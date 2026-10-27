# Background services

For Linux with systemd. `scripts/install-service.sh` and `scripts/demo.sh install` put these in place, with
`DAKKU_FOLDER` filled in as wherever Dakku's folder is.

- `dakku.service`: Dakku itself, starting with the PC and restarting if it ever stops
- `dakku-demo.service`: the demo, with made-up ducks
