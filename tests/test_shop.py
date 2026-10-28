"""The duck shop: friends earn grain for their focus and spend it on ducks; you have every duck."""
import json
import secrets
from datetime import date
from unittest import mock

from dakku import logic
from dakku.app import App, now_ms
from tests.test_together import TogetherTest


class ShopTest(TogetherTest):
    def setUp(self):
        super().setUp()
        # a few painted ducks, as published, beside Dakku's own ten
        ducks = self.app.web_dir / "ducks"
        ducks.mkdir()
        (ducks / "ducks.json").write_text(json.dumps({"kinds": {k: {"src": f"/ducks/{k}.webp"} for k in ("nurse", "sonic", "witch", "link")}}))
        self.group_ = self.group()
        self.mina = self.friend(self.group_, "Mina")
        self.month = mock.patch.object(App, "_today", return_value=date(2027, 1, 10))  # no holiday on
        self.month.start()
        self.addCleanup(self.month.stop)

    def shop(self, client):
        status, body, _ = client.call("GET", "/api/shop")
        self.assertEqual(status, 200, body)
        return body

    def studied(self, client, minutes, **extra):
        """A session synced from `client`'s device, as one run offline would be."""
        sid = f"s{secrets.token_hex(6)}"  # (two in the same millisecond still get their own)
        session = {"id": sid, "start": now_ms() - minutes * 60_000 - 3_600_000, "minutes": minutes, "tag": "Study", "updated": now_ms(), **extra}
        status, body, _ = client.call("POST", "/api/sync", {"ops": [{"op": "upsert", "session": session}]})
        self.assertEqual(status, 200, body)
        return body


class Earning(ShopTest):
    def test_the_rates_pay_more_for_longer_focus(self):
        pay = lambda m, **s: logic.grain_for({"minutes": m, "status": "done", "source": "dakku", **s})  # noqa: E731
        self.assertEqual([pay(m) for m in (5, 10, 25, 50, 90, 240)], [2, 10, 31, 75, 157, 315])
        self.assertEqual(pay(25, room="abc"), 34)  # together: a tenth more
        self.assertEqual(pay(60, status="withered"), 0)
        self.assertEqual(pay(60, manual=1), 0)
        self.assertEqual(pay(60, source="import"), 0)

    def test_a_timer_session_earns_grain_and_a_goal_day_a_bonus(self):
        self.assertEqual(self.shop(self.mina)["balance"], 0)
        self.start(self.mina, minutes=25)
        self.rewind(self.mina.person, 25)
        status, body, _ = self.mina.call("POST", "/api/timer", {"action": "finish"})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.shop(self.mina)["balance"], 31)  # 25 minutes, under the 30-minute goal
        self.studied(self.mina, 10)
        self.assertEqual(self.shop(self.mina)["balance"], 31 + 10 + logic.GRAIN_GOAL_DAY)  # and now the goal's reached

    def test_time_logged_by_hand_earns_nothing(self):
        self.studied(self.mina, 60, manual=True, source="manual")
        self.assertEqual(self.shop(self.mina)["balance"], 0)

    def test_you_have_every_duck_and_no_wallet(self):
        shop = self.shop(self.me)
        self.assertTrue(shop["owner"])
        self.assertNotIn("balance", shop)
        self.start(self.me, minutes=25, species="sonic")
        self.assertEqual(self.app.timer("me")["species"], "sonic")


class Owning(ShopTest):
    def test_a_friend_starts_with_the_plain_duck_and_unlocks_more_with_hours(self):
        self.assertEqual(self.shop(self.mina)["owned"], ["shiro"])
        self.studied(self.mina, 180)
        self.studied(self.mina, 180)  # six hours
        owned = self.shop(self.mina)["owned"]
        self.assertEqual(owned, ["shiro", "sailor", "neko"])

    def test_a_duck_you_dont_have_hatches_as_one_you_do(self):
        self.start(self.mina, minutes=25, species="sonic")
        self.assertEqual(self.app.timer(self.mina.person)["species"], "shiro")
        body = self.studied(self.mina, 30, species="sonic")
        self.assertNotEqual(body["sessions"][-1]["species"], "sonic")
        status, s, _ = self.mina.call("PUT", "/api/settings", {"species": "sonic", "randomSpecies": False})
        self.assertEqual(s["settings"]["species"], "shiro")

    def test_buying_a_duck(self):
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"duck": "sonic"})
        self.assertEqual(status, 402, body)
        for _ in range(4):
            self.studied(self.mina, 180)  # 4 × 315, and a goal day
        before = self.shop(self.mina)["balance"]
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"duck": "sonic"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["shop"]["balance"], before - logic.PRICE)
        self.assertIn("sonic", body["shop"]["owned"])
        self.start(self.mina, minutes=25, species="sonic")
        self.assertEqual(self.app.timer(self.mina.person)["species"], "sonic")
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"duck": "sonic"})
        self.assertEqual(status, 409, body)
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"duck": "king"})
        self.assertEqual(status, 400, body)  # it comes with hours

    def test_a_mystery_egg_is_a_duck_you_dont_have(self):
        for _ in range(8):
            self.studied(self.mina, 180)
        sellable = {k for k in logic.species() if logic.price(k) is not None and k not in logic.HOLIDAY}  # (January)
        got = set()
        while self.shop(self.mina)["mystery"]["left"]:
            status, body, _ = self.mina.call("POST", "/api/shop/mystery")
            self.assertEqual(status, 200, body)
            self.assertNotIn(body["duck"], got)
            got.add(body["duck"])
        self.assertEqual(got, sellable)
        status, body, _ = self.mina.call("POST", "/api/shop/mystery")
        self.assertEqual(status, 409, body)

    def test_a_holiday_duck_is_free_in_its_month_and_only_then(self):
        self.assertEqual(self.shop(self.mina)["catalog"]["witch"], {"event": "halloween", "month": 10, "inSeason": False})
        self.assertNotIn("witch", self.shop(self.mina)["owned"])
        App._today.return_value = date(2026, 10, 20)  # October
        self.assertIn("witch", self.shop(self.mina)["owned"])
        self.start(self.mina, minutes=25, species="witch")
        self.assertEqual(self.app.timer(self.mina.person)["species"], "witch")
        self.mina.call("POST", "/api/timer", {"action": "cancel", "undo": True})
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"duck": "witch"})
        self.assertEqual(status, 409, body)  # nothing to buy: it's hers this month already
        App._today.return_value = date(2026, 11, 2)  # after Halloween it's gone again
        self.assertNotIn("witch", self.shop(self.mina)["owned"])
        self.start(self.mina, minutes=25, species="witch")
        self.assertNotEqual(self.app.timer(self.mina.person)["species"], "witch")

    def test_themes_ponds_and_decorations_are_bought_too(self):
        shop = self.shop(self.mina)
        self.assertEqual(sorted(i for i in shop["ownedItems"]), ["pond:classic", "pond:seasonal", "pond:winter", "theme:ai"])
        self.assertEqual(shop["items"]["theme:sumi"], {"price": logic.THEME_PRICE})
        self.assertEqual(shop["items"]["pond:seasonal"], {"free": True})
        status, s, _ = self.mina.call("PUT", "/api/settings", {"theme": "sumi", "pondTheme": "night", "decor": ["koi"]})
        self.assertEqual((s["settings"]["theme"], s["settings"]["pondTheme"], s["settings"]["decor"]), ("ai", "seasonal", []))
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"item": "theme:sumi"})
        self.assertEqual(status, 402, body)
        for _ in range(6):
            self.studied(self.mina, 180)
        for item in ("theme:sumi", "decor:koi"):
            status, body, _ = self.mina.call("POST", "/api/shop/buy", {"item": item})
            self.assertEqual(status, 200, body)
        status, s, _ = self.mina.call("PUT", "/api/settings", {"theme": "sumi", "pondTheme": "night", "decor": ["koi", "torii"]})
        self.assertEqual((s["settings"]["theme"], s["settings"]["pondTheme"], s["settings"]["decor"]), ("sumi", "seasonal", ["koi"]))
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"item": "theme:sumi"})
        self.assertEqual(status, 409, body)

    def test_a_seasons_pond_is_free_while_it_lasts_and_bought_to_keep_it(self):
        self.assertEqual(self.shop(self.mina)["items"]["pond:winter"],
                         {"price": logic.POND_PRICE, "season": True, "inSeason": True, "bought": False})
        self.assertEqual(self.shop(self.mina)["items"]["pond:spring"]["inSeason"], False)
        status, s, _ = self.mina.call("PUT", "/api/settings", {"pondTheme": "winter"})  # January: free
        self.assertEqual(s["settings"]["pondTheme"], "winter")
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"item": "pond:winter"})
        self.assertEqual(status, 409, body)  # (nothing to buy while it's winter)
        App._today.return_value = date(2027, 4, 2)  # spring: winter's pond is over, the seasonal one takes over
        self.assertEqual(self.mina.call("GET", "/api/sync?since=0")[1]["settings"]["pondTheme"], "seasonal")
        self.assertIn("pond:spring", self.shop(self.mina)["ownedItems"])
        for _ in range(6):
            self.studied(self.mina, 180)
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"item": "pond:winter"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["shop"]["items"]["pond:winter"]["bought"], True)
        status, s, _ = self.mina.call("PUT", "/api/settings", {"pondTheme": "winter"})
        self.assertEqual(s["settings"]["pondTheme"], "winter")
        App._today.return_value = date(2027, 7, 2)  # still hers in summer
        self.assertEqual(self.mina.call("GET", "/api/sync?since=0")[1]["settings"]["pondTheme"], "winter")
        self.assertNotIn("pond:spring", self.shop(self.mina)["ownedItems"])

    def test_a_holidays_theme_and_pond_are_free_while_it_is_on_and_go_when_it_ends(self):
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"item": "theme:christmas"})
        self.assertEqual(status, 400, body)
        App._today.return_value = date(2026, 12, 20)
        status, s, _ = self.mina.call("PUT", "/api/settings", {"theme": "christmas", "pondTheme": "christmas"})
        self.assertEqual((s["settings"]["theme"], s["settings"]["pondTheme"]), ("christmas", "christmas"))
        App._today.return_value = date(2027, 1, 3)  # Christmas is over: back to the free ones
        status, body, _ = self.mina.call("GET", "/api/sync?since=0")
        self.assertEqual((body["settings"]["theme"], body["settings"]["pondTheme"]), ("ai", "seasonal"))
        App._today.return_value = date(2027, 2, 10)  # four days after Lunar New Year 2027
        self.assertIn("theme:lunar", self.shop(self.mina)["ownedItems"])
        App._today.return_value = date(2027, 2, 25)  # past the Lantern Festival
        self.assertNotIn("theme:lunar", self.shop(self.mina)["ownedItems"])

    def test_turning_the_shop_off_gives_friends_every_duck(self):
        self.me.call("PUT", "/api/settings", {"shopForFriends": False})
        self.assertEqual(self.shop(self.mina), {"on": False})
        self.start(self.mina, minutes=25, species="sonic")
        self.assertEqual(self.app.timer(self.mina.person)["species"], "sonic")
        status, body, _ = self.mina.call("POST", "/api/shop/buy", {"duck": "link"})
        self.assertEqual(status, 400, body)

    def test_you_can_use_the_shop_too(self):
        self.me.call("PUT", "/api/settings", {"theme": "sumi", "species": "sonic", "randomSpecies": False})
        self.me.call("PUT", "/api/settings", {"shopForMe": True})
        shop = self.shop(self.me)
        self.assertTrue(shop["owner"] and shop["on"])
        self.assertEqual(shop["owned"], ["shiro"])
        self.assertIn("requests", shop)  # (still yours to answer)
        settings = self.me.call("GET", "/api/sync?since=0")[1]["settings"]
        self.assertEqual((settings["species"], settings["theme"]), ("shiro", "ai"))
        self.studied(self.me, 180)
        self.studied(self.me, 180)
        self.studied(self.me, 180)
        self.studied(self.me, 180)
        status, body, _ = self.me.call("POST", "/api/shop/buy", {"duck": "sonic"})
        self.assertEqual(status, 200, body)
        self.me.call("PUT", "/api/settings", {"shopForMe": False})
        self.assertEqual(self.shop(self.me)["forMe"], False)
        self.start(self.me, minutes=25, species="link")
        self.assertEqual(self.app.timer("me")["species"], "link")

    def test_a_friend_cant_turn_the_shop_off(self):
        self.mina.call("PUT", "/api/settings", {"shopForFriends": False, "shopForMe": True})
        self.assertTrue(self.shop(self.mina)["on"])
        self.assertTrue(self.shop(self.me)["owner"] and not self.shop(self.me)["forMe"])


class Requests(ShopTest):
    def test_a_requested_duck_goes_to_its_requester_and_into_the_shop(self):
        for _ in range(13):
            self.studied(self.mina, 180)
        before = self.shop(self.mina)["balance"]
        status, body, _ = self.mina.call("POST", "/api/shop/requests", {"text": "A duck dressed as a strawberry"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["shop"]["balance"], before - logic.CUSTOM_PRICE)
        rid = body["request"]["id"]
        self.assertEqual(self.shop(self.me)["requests"][-1]["name"], "Mina")
        status, body, _ = self.door().call("POST", f"/api/shop/requests/{rid}", {"duck": "link"})
        self.assertIn(status, (401, 403, 404), body)  # yours only (and not even there, at the friends' door)
        status, body, _ = self.me.call("POST", f"/api/shop/requests/{rid}", {"duck": "link"})
        self.assertEqual(status, 200, body)
        self.assertIn("link", self.shop(self.mina)["owned"])
        kai = self.friend(self.group_, "Kai")
        for _ in range(4):
            self.studied(kai, 180)
        self.assertEqual(self.shop(kai)["catalog"]["link"], {"price": logic.PRICE})
        status, body, _ = kai.call("POST", "/api/shop/buy", {"duck": "link"})
        self.assertEqual(status, 200, body)

    def test_a_request_can_be_refunded(self):
        for _ in range(13):
            self.studied(self.mina, 180)
        before = self.shop(self.mina)["balance"]
        _, body, _ = self.mina.call("POST", "/api/shop/requests", {"text": "A duck with a tiny umbrella"})
        status, body, _ = self.me.call("POST", f"/api/shop/requests/{body['request']['id']}", {"refund": True})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.shop(self.mina)["balance"], before)

    def test_a_request_needs_enough_grain(self):
        status, body, _ = self.mina.call("POST", "/api/shop/requests", {"text": "A duck in a spacesuit"})
        self.assertEqual(status, 402, body)


class Holidays(ShopTest):
    def look(self, client):
        settings = client.call("GET", "/api/sync?since=0")[1]["settings"]
        return settings["theme"], settings["pondTheme"]

    def test_a_holiday_comes_on_by_itself_and_what_was_before_comes_back(self):
        self.me.call("PUT", "/api/settings", {"theme": "sumi", "pondTheme": "night"})
        App._today.return_value = date(2026, 10, 5)
        self.assertEqual(self.look(self.me), ("halloween", "halloween"))
        App._today.return_value = date(2026, 11, 2)
        self.assertEqual(self.look(self.me), ("thanksgiving", "thanksgiving"))
        App._today.return_value = date(2026, 12, 1)
        self.assertEqual(self.look(self.me), ("christmas", "christmas"))
        App._today.return_value = date(2027, 1, 2)
        self.assertEqual(self.look(self.me), ("sumi", "night"))
        App._today.return_value = date(2027, 2, 6)  # Lunar New Year
        self.assertEqual(self.look(self.me), ("lunar", "lunar"))

    def test_switched_off_during_a_holiday_it_stays_off(self):
        App._today.return_value = date(2026, 10, 5)
        self.assertEqual(self.look(self.me), ("halloween", "halloween"))
        self.me.call("PUT", "/api/settings", {"theme": "yozakura", "pondTheme": "sakura"})
        App._today.return_value = date(2026, 10, 20)
        self.assertEqual(self.look(self.me), ("yozakura", "sakura"))
        App._today.return_value = date(2026, 11, 3)  # (until the next one)
        self.assertEqual(self.look(self.me), ("thanksgiving", "thanksgiving"))

    def test_a_friend_gets_the_holiday_free_and_their_own_back_after(self):
        App._today.return_value = date(2026, 12, 3)
        self.assertEqual(self.look(self.mina), ("christmas", "christmas"))
        App._today.return_value = date(2027, 1, 3)
        self.assertEqual(self.look(self.mina), ("ai", "classic"))

    def test_it_can_be_turned_off(self):
        self.me.call("PUT", "/api/settings", {"holidayAuto": False, "theme": "sumi"})
        App._today.return_value = date(2026, 10, 5)
        self.assertEqual(self.look(self.me), ("sumi", "classic"))
