# Tests

```bash
python3 -m unittest discover -s tests
```

- `test_api.py`: the server over real HTTP: sign-in, the timer, sync, settings, streaks, recaps, limits, backups
- `test_together.py`: friends, groups, joining sessions, the friends' door and cheers
- `test_ducks.py`: the duck list, and that every picture is in style
- `test_crypto.py`: the push notification encryption and signatures
- `test_demo.py`: the demo
- `test_lofi.py`: matching the playlist's songs
