# Scripts

Setting it up on a PC (each says at the top what it does, and how to undo it):

- `install-service.sh`: run Dakku in the background, starting with the PC
- `enable-https.sh`: a secure address on Tailscale, which iPhone notifications need
- `enable-friends.sh`: open the friends' door, so friends can join without installing anything
- `install-shortcut.sh`: a Dakku app on the dock
- `always-on.sh`: keep the PC awake, with the screens turning off by themselves
- `demo.sh`: run the demo, with made-up ducks

Making the art:

- `duck.py`: makes a new duck: its ChatGPT prompt, then checks and finishes the picture
- `import_art.py`: brings ChatGPT's pictures in: ducks, eggs, ponds, ripples, decorations and the icon
- `lofi.py`: finds each song of the lofi playlist on YouTube
- `make_icons.py`: the first, drawn app icon

The playable demo on GitHub Pages:

- `static-demo/`: builds the demo as a website that runs on its own in the browser, no PC needed
