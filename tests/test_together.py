"""Studying together: friends, groups, invites, the friends' door, and sessions anyone can join."""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from dakku.app import MINUTE, App, now_ms
from dakku.store import Store
from dakku.web import Server, make_handler
from tests.test_api import Client


class TogetherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        web = root / "web"
        web.mkdir()
        (web / "index.html").write_text("<!doctype html><title>Dakku</title>")
        self.app = App(root / "data", web, anki_url=None, start_threads=False)
        self.servers = []
        self.port = self._serve(make_handler(self.app))
        self.friends_port = self._serve(make_handler(self.app, public=True))
        self.app.port = self.port
        self.app._addresses_cache = (9e18, {"lan": [], "tailnet": None, "https": None, "friends": "https://pc.example.ts.net:8443"})
        self.me = Client(self.port)  # you, on this PC
        # someone on the internet, relayed to the friends' door by Funnel (which connects from this PC)
        self.door = lambda: Client(self.friends_port, host="pc.example.ts.net:8443", extra={"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https"})

    def _serve(self, handler):
        server = Server(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.servers.append(server)
        return server.server_address[1]

    def tearDown(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.app.close()
        self.tmp.cleanup()

    # helpers
    def group(self, name="Us"):
        status, group, _ = self.me.call("POST", "/api/groups", {"name": name})
        self.assertEqual(status, 200, group)
        return group

    def invite(self, group, **extra):
        status, invite, _ = self.me.call("POST", "/api/invites", {"group": group["id"], **extra})
        self.assertEqual(status, 200, invite)
        return invite

    def friend(self, group, name="Mina"):
        client = self.door()
        status, body, _ = client.call("POST", "/api/join", {"code": self.invite(group)["code"], "name": name})
        self.assertEqual(status, 200, body)
        client.person = body["person"]["id"]
        return client

    def start(self, client, minutes=60, **extra):
        status, body, _ = client.call("POST", "/api/timer", {"action": "start", "minutes": minutes, **extra})
        self.assertEqual(status, 200, body)
        return body["timer"]

    def rewind(self, pid, minutes):
        """Pretend `pid`'s timer started `minutes` earlier."""
        key = self.app._key("timer", pid)
        t = self.app.store.get(key)
        t.update(startedAt=t["startedAt"] - minutes * MINUTE, runFrom=t["runFrom"] - minutes * MINUTE)
        self.app.store.set(key, t)


class Invites(TogetherTest):
    def test_a_friend_joins_with_an_invite(self):
        group = self.group()
        invite = self.invite(group)
        self.assertTrue(invite["url"].startswith("https://pc.example.ts.net:8443/join#"))
        mina = self.door()
        status, body, _ = mina.call("POST", "/api/join", {"code": invite["code"], "name": "Mina", "mark": "🐱"})
        self.assertEqual(status, 200, body)
        me = mina.call("GET", "/api/whoami")[1]
        self.assertEqual((me["role"], me["person"]["name"], me["person"]["mark"], me["trusted"]), ("friend", "Mina", "🐱", False))
        together = mina.call("GET", "/api/together")[1]
        self.assertEqual([g["name"] for g in together["groups"]], ["Us"])
        self.assertEqual({p["name"] for p in together["people"]}, {"Me", "Mina"})

    def test_the_join_page_can_say_who_its_from(self):
        self.me.call("PATCH", "/api/people/me", {"name": "Sam"})
        invite = self.invite(self.group("Study club"))
        status, peek, _ = self.door().call("POST", "/api/invite", {"code": invite["code"]})
        self.assertEqual((status, peek["from"], peek["group"], peek["people"]), (200, "Sam", "Study club", ["Sam"]))
        self.assertEqual(self.door().call("POST", "/api/invite", {"code": "nope"})[0], 404)
        self.assertEqual(self.door().call("POST", "/api/join", {"code": invite["code"], "name": "Mina"})[0], 200)  # peeking used nothing

    def test_invites_run_out_expire_and_can_be_taken_back(self):
        group = self.group()
        once = self.invite(group, uses=1)
        self.assertEqual(self.door().call("POST", "/api/join", {"code": once["code"], "name": "A"})[0], 200)
        self.assertEqual(self.door().call("POST", "/api/join", {"code": once["code"], "name": "B"})[0], 401)
        taken = self.invite(group)
        self.assertEqual(self.me.call("DELETE", f"/api/invites/{taken['id']}")[0], 200)
        self.assertEqual(self.door().call("POST", "/api/join", {"code": taken["code"], "name": "C"})[0], 401)
        old = self.invite(group)
        self.app.store.db.execute("UPDATE invites SET expires=? WHERE id=?", (now_ms() - 1, old["id"]))
        self.assertEqual(self.door().call("POST", "/api/join", {"code": old["code"], "name": "D"})[0], 401)

    def test_guessing_codes_is_rate_limited(self):
        guesser = self.door()
        for _ in range(5):
            self.assertEqual(guesser.call("POST", "/api/join", {"code": "nope", "name": "x"})[0], 401)
        self.assertEqual(guesser.call("POST", "/api/join", {"code": self.invite(self.group())["code"], "name": "x"})[0], 429)

    def test_strangers_guessing_cant_lock_you_out(self):
        # wrong pairing codes from all over the internet close the friends' door to pairing codes for a
        # while, never yours; and invites, too long to guess, keep working for the friends they're for
        stranger = lambda n: Client(self.friends_port, host="pc.example.ts.net:8443",  # noqa: E731
                                    extra={"X-Forwarded-For": f"198.51.100.{n}", "X-Forwarded-Proto": "https"})
        with mock.patch("dakku.app.time.sleep"):  # (each wrong code waits a moment: not here)
            for n in range(40):
                self.assertEqual(stranger(n).call("POST", "/api/login", {"pair": "123456"})[0], 401)
        self.assertEqual(stranger(99).call("POST", "/api/login", {"pair": "123456"})[0], 429)
        code = self.me.call("POST", "/api/pair")[1]["code"]
        phone = Client(self.port, host="pc.example.ts.net", extra={"X-Forwarded-For": "100.1.2.3"})
        self.assertEqual(phone.call("POST", "/api/login", {"pair": code})[0], 200)
        invite = self.invite(self.group())
        self.assertEqual(self.door().call("POST", "/api/invite", {"code": invite["code"]})[0], 200)
        self.assertEqual(self.door().call("POST", "/api/join", {"code": invite["code"], "name": "Mina"})[0], 200)

    def test_strangers_getting_invites_wrong_dont_hold_up_a_real_one(self):
        for n in range(60):
            stranger = Client(self.friends_port, host="pc.example.ts.net:8443", extra={"X-Forwarded-For": f"198.51.100.{n}", "X-Forwarded-Proto": "https"})
            self.assertEqual(stranger.call("POST", "/api/invite", {"code": "nope"})[0], 404)
        invite = self.invite(self.group())
        self.assertEqual(self.door().call("POST", "/api/join", {"code": invite["code"], "name": "Mina"})[0], 200)

    def test_a_made_up_address_doesnt_dodge_the_limit(self):
        # Tailscale adds the address it really saw at the end; whatever a browser sent itself comes first
        for n in range(5):
            spoofer = Client(self.friends_port, host="pc.example.ts.net:8443", extra={"X-Forwarded-For": f"10.0.0.{n}, 203.0.113.9", "X-Forwarded-Proto": "https"})
            self.assertEqual(spoofer.call("POST", "/api/invite", {"code": "nope"})[0], 404)
        self.assertEqual(self.door().call("POST", "/api/invite", {"code": "nope"})[0], 429)

    def test_a_friends_own_code_signs_in_their_other_device(self):
        mina = self.friend(self.group())
        status, pair, _ = mina.call("POST", "/api/pair")
        self.assertEqual(status, 200, pair)
        home_screen = self.door()
        self.assertEqual(home_screen.call("POST", "/api/login", {"pair": pair["code"]})[0], 200)
        self.assertEqual(home_screen.call("GET", "/api/whoami")[1]["person"]["id"], mina.person)

    def test_your_codes_and_passcode_dont_work_at_the_friends_door(self):
        code = self.me.call("POST", "/api/pair")[1]["code"]
        self.assertEqual(self.door().call("POST", "/api/login", {"pair": code})[0], 401)
        self.assertEqual(self.door().call("POST", "/api/login", {"passcode": self.app.passcode_plain()})[0], 401)

    def test_sign_in_links_for_a_friends_new_phone(self):
        group = self.group()
        mina = self.friend(group)
        link = self.invite(group, person=mina.person)
        phone = self.door()
        self.assertEqual(phone.call("POST", "/api/join", {"code": link["code"]})[0], 200)
        self.assertEqual(phone.call("GET", "/api/whoami")[1]["person"]["id"], mina.person)


class TheFriendsDoor(TogetherTest):
    def test_nobody_there_is_this_pc(self):
        here = Client(self.friends_port)  # straight from this PC, no proxy headers at all
        self.assertFalse(here.call("GET", "/api/whoami")[1]["trusted"])
        self.assertEqual(here.call("GET", "/api/bootstrap")[0], 401)

    def test_only_what_friends_need(self):
        mina = self.friend(self.group())
        for method, path in (("GET", "/api/passcode"), ("POST", "/api/passcode"), ("POST", "/api/import"), ("GET", "/api/anki"),
                             ("GET", "/api/people"), ("POST", "/api/invites"), ("POST", "/api/groups")):
            self.assertEqual(mina.call(method, path, {} if method == "POST" else None)[0], 404, path)

    def test_a_friends_sign_in_never_reaches_your_door(self):
        mina = self.friend(self.group())
        self.assertTrue(mina.cookie.startswith("dakku_friend="))
        # the same browser, on your door: her cookie (under its own name) isn't yours to read
        same_browser = Client(self.port, host="pc.example.ts.net", extra={"X-Forwarded-For": "100.1.2.3", "Cookie": mina.cookie})
        self.assertEqual(same_browser.call("GET", "/api/bootstrap")[0], 401)
        # and this PC is always you, even with a friend's token
        token = mina.cookie.split("=", 1)[1]
        here = Client(self.port, extra={"Authorization": f"Bearer {token}"})
        self.assertEqual(here.call("GET", "/api/whoami")[1]["role"], "owner")

    def test_your_admin_is_yours_alone(self):
        group = self.group()
        mina = self.friend(group)
        # if Mina could reach your own door (say she's on your Tailscale), she still can't run it
        token = mina.cookie.split("=", 1)[1]
        inside = Client(self.port, host="pc.example.ts.net", extra={"X-Forwarded-For": "100.1.2.3", "Authorization": f"Bearer {token}"})
        self.assertEqual(inside.call("GET", "/api/people")[0], 403)
        self.assertEqual(inside.call("POST", "/api/invites", {"group": group["id"]})[0], 403)
        self.assertEqual(inside.call("POST", "/api/import", {"data": {"sessions": []}})[0], 403)


class Privacy(TogetherTest):
    def test_everyone_has_their_own_pond(self):
        mina = self.friend(self.group())
        mine = {"id": "my-session", "start": now_ms() - 60 * MINUTE, "minutes": 30, "tag": "CCNA"}
        self.assertEqual(self.me.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": mine}]})[0], 200)
        hers = mina.call("GET", "/api/sync?since=0")[1]
        self.assertEqual(hers["sessions"], [])
        self.assertEqual(hers["settings"]["tags"][0]["name"], "Study")  # her own tags, not yours
        # she can't change or delete yours, even knowing its id
        mina.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": dict(mine, minutes=1, updated=now_ms() + 1000)},
                                                {"op": "delete", "id": "my-session", "updated": now_ms() + 1000}]})
        row = self.app.store.get_session("my-session")
        self.assertEqual((row["minutes"], row["deleted"], row["person"]), (30, 0, "me"))
        # and her sessions are hers
        mina.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": {"id": "her-session", "start": now_ms() - MINUTE * 50, "minutes": 20}}]})
        self.assertEqual(self.app.store.get_session("her-session")["person"], mina.person)
        self.assertNotIn("her-session", [s["id"] for s in self.me.call("GET", "/api/sync?since=0")[1]["sessions"]])

    def test_removing_someone_signs_them_out(self):
        group = self.group()
        mina = self.friend(group)
        self.assertEqual(self.me.call("DELETE", f"/api/people/{mina.person}")[0], 200)
        self.assertEqual(mina.call("GET", "/api/bootstrap")[0], 401)
        self.assertEqual(self.me.call("GET", f"/api/groups/{group['id']}")[1]["group"]["members"], ["me"])

    def test_you_can_edit_your_own_profile(self):
        self.assertEqual(self.me.call("PATCH", "/api/people/me", {"name": "Sam", "mark": "S"})[1]["name"], "Sam")
        self.assertEqual(self.app.settings()["name"], "Sam")
        self.assertEqual(self.me.call("DELETE", "/api/people/me")[0], 400)

    def test_profiles(self):
        group = self.group()
        mina, kai = self.friend(group, "Mina"), self.friend(group, "Kai")
        self.assertEqual(mina.call("PATCH", f"/api/people/{mina.person}", {"name": "Mina M", "mark": "M", "color": "#D9568F"})[0], 200)
        self.assertEqual(mina.call("PATCH", f"/api/people/{kai.person}", {"name": "nope"})[0], 403)
        self.assertEqual(self.me.call("PATCH", f"/api/people/{kai.person}", {"mark": "K"})[0], 200)
        names = {p["id"]: (p["name"], p["mark"]) for p in mina.call("GET", "/api/together")[1]["people"]}
        self.assertEqual(names[mina.person], ("Mina M", "M"))
        self.assertEqual(names[kai.person], ("Kai", "K"))

    def test_leaving_a_group(self):
        group = self.group()
        mina = self.friend(group)
        self.assertEqual(mina.call("DELETE", f"/api/groups/{group['id']}/members/me")[0], 403)
        self.assertEqual(mina.call("DELETE", f"/api/groups/{group['id']}/members/{mina.person}")[0], 200)
        self.assertEqual(mina.call("GET", "/api/together")[1]["groups"], [])


class StudyingTogether(TogetherTest):
    def test_join_in_the_middle_and_both_hatch(self):
        group = self.group()
        mina = self.friend(group)
        mine = self.start(self.me, 120, species="ninja", tag="CCNA")
        # for its first seconds you can still call it off, so friends don't see it yet
        self.assertEqual(mina.call("GET", "/api/together")[1]["rooms"], [])
        self.rewind("me", 1)
        rooms = mina.call("GET", "/api/together")[1]["rooms"]
        self.assertEqual([r["id"] for r in rooms], [mine["id"]])
        status, joined, _ = mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"], "species": "neko", "tag": "Reading"})
        self.assertEqual(status, 200, joined)
        self.assertEqual([g["person"] for g in joined["timer"]["party"]], ["me", mina.person])
        self.assertEqual(joined["timer"]["hostTimer"]["id"], mine["id"])
        # you're halfway when she joins; she studies the second hour with you
        self.rewind("me", 119)
        self.rewind(mina.person, 60)
        self.app._check_timers(now_ms())
        my_duck = self.app.store.get_session(mine["id"])
        her_duck = next(s for s in self.app.store.sessions(person=mina.person))
        self.assertEqual((my_duck["minutes"], my_duck["species"], my_duck["room"]), (120, "ninja", mine["id"]))
        self.assertEqual((her_duck["minutes"], her_duck["species"], her_duck["status"], her_duck["room"]), (60, "neko", "done", mine["id"]))
        self.assertIsNone(self.app.store.get(self.app._key("timer", mina.person)))
        pond = self.me.call("GET", f"/api/groups/{group['id']}")[1]
        # your own pond has your two hours; the group pond, the hour you studied together, for each of you
        self.assertEqual(sorted((s["person"], s["minutes"]) for s in pond["pond"]), sorted([("me", 60), (mina.person, 60)]))
        self.assertEqual(next(s["own"] for s in pond["pond"] if s["person"] == "me"), 120)

    def test_leave_early_with_your_own_duck(self):
        group = self.group()
        mina = self.friend(group)
        mine = self.start(self.me, 90)
        mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"]})
        self.rewind(mina.person, 25)
        status, left, _ = mina.call("POST", "/api/timer", {"action": "finish"})
        self.assertEqual((left["session"]["minutes"], left["session"]["status"]), (25, "done"))
        self.assertIsNotNone(self.app.store.get("timer"))  # you keep going
        self.rewind("me", 90)
        self.app._check_timers(now_ms())
        self.assertEqual(len(self.me.call("GET", f"/api/groups/{group['id']}")[1]["pond"]), 2)

    def test_if_the_host_gives_up_guests_still_get_their_ducks(self):
        mina = self.friend(self.group())
        mine = self.start(self.me, 60)
        mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"]})
        self.rewind("me", 20)
        self.rewind(mina.person, 15)
        self.me.call("POST", "/api/timer", {"action": "cancel"})
        self.assertEqual(self.app.store.get_session(mine["id"])["status"], "withered")
        her = self.app.store.sessions(person=mina.person)
        self.assertEqual([(s["minutes"], s["status"]) for s in her], [(15, "done")])

    def test_a_guest_giving_up_goes_cold_alone(self):
        mina = self.friend(self.group())
        mine = self.start(self.me, 60)
        mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"]})
        self.rewind(mina.person, 10)
        self.assertEqual(mina.call("POST", "/api/timer", {"action": "cancel"})[1]["session"]["status"], "withered")
        self.assertIsNotNone(self.app.store.get("timer"))

    def test_who_can_join(self):
        group = self.group()
        mina = self.friend(group)
        other = self.group("Other")
        stranger = self.friend(other, "Stranger")
        self.me.call("DELETE", f"/api/groups/{other['id']}/members/me")  # so you two share no group
        mine = self.start(self.me, 60)
        self.assertEqual(stranger.call("POST", "/api/timer", {"action": "join", "room": mine["id"]})[0], 403)
        self.assertEqual(stranger.call("GET", "/api/together")[1]["rooms"], [])
        self.assertEqual(mina.call("POST", "/api/timer", {"action": "join", "room": "no-such-session"})[0], 404)
        self.start(mina, 25)
        self.assertEqual(mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"]})[0], 409)  # her own first
        self.me.call("POST", "/api/timer", {"action": "cancel"})
        closed = self.start(self.me, 60, open=False)
        mina.call("POST", "/api/timer", {"action": "cancel"})
        self.assertEqual(mina.call("POST", "/api/timer", {"action": "join", "room": closed["id"]})[0], 403)

    def test_the_group_pond_is_only_what_you_did_together(self):
        group = self.group()
        mina = self.friend(group)
        # a session on your own, and one of hers: not in the group pond
        self.me.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": {"id": "solo-mine", "start": now_ms() - 5 * 3600_000, "minutes": 45, "tag": "CCNA"}}]})
        mina.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": {"id": "solo-hers", "start": now_ms() - 4 * 3600_000, "minutes": 30, "tag": "Study"}}]})
        mine = self.start(self.me, 60, tag="CCNA")
        mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"], "tag": "Study"})
        self.rewind("me", 60)
        self.rewind(mina.person, 40)
        self.app._check_timers(now_ms())
        view = mina.call("GET", f"/api/groups/{group['id']}")[1]
        self.assertEqual(sorted(s["id"] for s in view["pond"]), sorted([mine["id"], next(s["id"] for s in view["pond"] if s["person"] == mina.person)]))
        board = {b["person"]: b for b in view["board"]}
        self.assertEqual((board["me"]["total"], board["me"]["together"]), (105, 40))
        self.assertEqual((board[mina.person]["total"], board[mina.person]["together"]), (70, 40))
        self.assertEqual(board[mina.person]["tags"][0]["name"], "Study")
        self.assertEqual((view["stats"]["sessions"], view["stats"]["minutes"]), (1, 80))

    def test_the_host_sees_who_joined(self):
        mina = self.friend(self.group())
        mine = self.start(self.me, 60)
        mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"], "species": "kitsune"})
        party = self.me.call("GET", "/api/timer")[1]["timer"]["party"]
        self.assertEqual([(g["person"], g["host"]) for g in party], [("me", True), (mina.person, False)])
        self.assertEqual(party[1]["species"], "kitsune")


    def test_the_first_seconds_can_be_called_off(self):
        mina = self.friend(self.group())
        told = []
        self.app._notify_started = lambda host, t: told.append(host)
        self.start(self.me, 60)
        self.app._check_timers(now_ms())
        self.assertEqual(told, [])  # not yet
        status, body, _ = self.me.call("POST", "/api/timer", {"action": "cancel", "undo": True})
        self.assertEqual((status, body["session"]), (200, None))  # no cold egg, nothing logged
        self.assertEqual(self.app.store.sessions(), [])
        self.app._check_timers(now_ms())
        self.assertEqual(told, [])  # and nobody heard about it
        self.start(self.me, 60)
        self.rewind("me", 1)
        self.app._check_timers(now_ms())
        self.assertEqual(told, ["me"])  # past the first seconds, friends hear about it once
        self.app._check_timers(now_ms())
        self.assertEqual(told, ["me"])
        self.assertEqual(len(mina.call("GET", "/api/together")[1]["rooms"]), 1)


class Cheers(TogetherTest):
    def cheer(self, client, to, text="You've got this!"):
        return client.call("POST", "/api/cheer", {"to": to, "text": text})

    def test_cheer_on_someone_studying(self):
        mina = self.friend(self.group())
        self.start(mina, 60)
        self.rewind(mina.person, 1)
        status, body, _ = self.cheer(self.me, mina.person, "  You've   got this! 🔥 ")
        self.assertEqual(status, 200, body)
        cheers = mina.call("GET", "/api/timer")[1]["timer"]["cheers"]
        self.assertEqual([(c["from"], c["text"]) for c in cheers], [("me", "You've got this! 🔥")])
        self.assertTrue(cheers[0]["name"])
        # and she can cheer you back
        self.start(self.me, 30)
        self.rewind("me", 1)
        self.assertEqual(self.cheer(mina, "me", "Keep going!")[0], 200)
        self.assertEqual([c["text"] for c in self.me.call("GET", "/api/timer")[1]["timer"]["cheers"]], ["Keep going!"])

    def test_only_people_you_could_join(self):
        group = self.group()
        mina = self.friend(group)
        other = self.group("Other")
        stranger = self.friend(other, "Stranger")
        self.me.call("DELETE", f"/api/groups/{other['id']}/members/me")  # so you two share no group
        self.assertEqual(self.cheer(self.me, mina.person)[0], 409)  # she isn't studying
        self.start(mina, 60)
        self.rewind(mina.person, 1)
        self.assertEqual(self.cheer(stranger, mina.person)[0], 409)  # not in a group with her
        self.assertEqual(self.cheer(self.me, mina.person, "   ")[0], 400)
        self.assertEqual(self.cheer(mina, mina.person)[0], 400)
        mina.call("POST", "/api/timer", {"action": "cancel"})
        self.start(mina, 60, open=False)
        self.rewind(mina.person, 1)
        self.assertEqual(self.cheer(self.me, mina.person)[0], 409)  # a session she keeps to herself

    def test_not_too_often(self):
        mina = self.friend(self.group())
        self.start(mina, 60)
        self.rewind(mina.person, 1)
        self.assertEqual(self.cheer(self.me, mina.person, "x" * 500)[0], 200)
        self.assertEqual(len(self.app.store.get(self.app._key("cheers", mina.person))[0]["text"]), 140)  # kept short
        self.assertEqual(self.cheer(self.me, mina.person, "And again")[0], 429)

    def test_cheers_stay_with_their_session(self):
        mina = self.friend(self.group())
        self.start(mina, 60)
        self.rewind(mina.person, 1)
        self.cheer(self.me, mina.person)
        mina.call("POST", "/api/timer", {"action": "cancel"})
        self.start(mina, 30)
        self.assertEqual(mina.call("GET", "/api/timer")[1]["timer"]["cheers"], [])


class Pomodoro(TogetherTest):
    def pomo(self, client, focus=25, brk=5, rounds=4, **extra):
        return self.start(client, mode="pomo", pomo={"focus": focus, "brk": brk, "rounds": rounds}, **extra)

    def test_focus_and_breaks(self):
        t = self.pomo(self.me)
        self.assertEqual((t["mode"], t["planned"], t["phase"], t["round"]), ("pomo", 115 * MINUTE, "focus", 1))
        self.rewind("me", 27)
        v = self.me.call("GET", "/api/timer")[1]["timer"]
        self.assertEqual((v["phase"], v["round"], round(v["phaseLeft"] / MINUTE), round(v["focused"] / MINUTE)), ("break", 1, 3, 25))
        self.rewind("me", 88)  # all four rounds
        self.app._check_timers(now_ms())
        duck = self.app.store.sessions()[0]
        self.assertEqual((duck["minutes"], duck["rounds"], duck["status"]), (100, 4, "done"))  # the breaks don't count

    def test_stop_after_a_few_rounds(self):
        self.pomo(self.me)
        self.rewind("me", 57)  # on the second break
        session = self.me.call("POST", "/api/timer", {"action": "finish"})[1]["session"]
        self.assertEqual((session["minutes"], session["rounds"]), (50, 2))

    def test_breaks_are_announced(self):
        heard = []
        self.app._notify_phase = lambda pid, t, rnd, phase, timers: heard.append((rnd, phase))
        self.pomo(self.me)
        self.rewind("me", 26)
        self.app._check_timers(now_ms())
        self.rewind("me", 5)
        self.app._check_timers(now_ms())
        self.app._check_timers(now_ms())
        self.assertEqual(heard, [(1, "break"), (2, "focus")])

    def test_joining_a_pomodoro_counts_only_its_focus(self):
        mina = self.friend(self.group())
        mine = self.pomo(self.me)
        self.rewind("me", 20)
        mina.call("POST", "/api/timer", {"action": "join", "room": mine["id"]})
        self.rewind("me", 40)  # you're 60 minutes in: two rounds and a break done; she was there for 30 of focus
        self.rewind(mina.person, 40)
        session = mina.call("POST", "/api/timer", {"action": "finish"})[1]["session"]
        self.assertEqual(session["minutes"], 30)


class Upgrade(unittest.TestCase):
    def test_an_older_dakku_becomes_yours(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dakku.db"
            db = sqlite3.connect(path)
            db.executescript("""
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE sessions (id TEXT PRIMARY KEY, start INTEGER NOT NULL, minutes INTEGER NOT NULL, tag TEXT NOT NULL DEFAULT '',
                  species TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'done', source TEXT NOT NULL DEFAULT '',
                  manual INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', updated INTEGER NOT NULL, rev INTEGER NOT NULL,
                  deleted INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE devices (id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, name TEXT NOT NULL, created INTEGER NOT NULL,
                  last_seen INTEGER NOT NULL, last_ip TEXT NOT NULL DEFAULT '');
                INSERT INTO sessions(id, start, minutes, updated, rev) VALUES ('old-one', 1700000000000, 25, 1700000000000, 1);
                INSERT INTO devices VALUES ('phone', 'hash', 'iPhone', 1, 1, '');
            """)
            db.close()
            store = Store(path)
            self.assertEqual(store.get_session("old-one")["person"], "me")
            self.assertEqual(store.devices("me")[0]["id"], "phone")
            store.db.close()


if __name__ == "__main__":
    unittest.main()
