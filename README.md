# Hermes's Skills

**Author:** Francisco Moniz ([@franzmoniz](https://github.com/franzmoniz))  -  **License:** MIT

These are skills for the [Hermes agent](https://hermes-agent.nousresearch.com/docs). Each one teaches
your Hermes to do something new. Every folder has two parts:

- a `README.md` for **you**: what the skill does, why it is useful, and what you will be asked to do;
- a `SKILL.md` for **your Hermes**: the full step-by-step procedure it follows. It checks what you
  already have before installing anything, and it asks you only for what it can't do itself.

Nothing in here contains anybody's personal data. Every installation is set up from zero for the person
installing it.

## Skills

| Skill | What it does | Platforms |
|---|---|---|
| [Hermes Device Sync](hermes-device-sync) - *One Hermes on all your devices* | Links your laptop, desktop, server and phone so they work as one Hermes. Memory and skills are shared. The conversation follows you and is saved after every answer. Every device gets the same AI accounts and logins (checked automatically). Only one Hermes open at a time (it asks before opening a second one). Plus file sharing, an activity log, a request queue for devices that are off, offline work (optional local AI model when there is no internet), an optional encrypted vault shared by all devices, and optional remote control. | Windows, Linux, macOS |
| [Hermes Model Return](hermes-model-return) - *Always back to your best AI model* | Every prompt, if you are on a fallback model, it tests the models above and switches back to the best one that answers (no more waiting hours for a cooldown, and it climbs up from a local model when the internet returns). Never overrides a model you chose by hand: it reminds you every 5 prompts instead. | Windows, Linux, macOS |
| [Hermes Quick Launch](hermes-quick-launch) - *Open Hermes from Win+R* | Press Win+R, type `hermes`, and Hermes opens in Windows Terminal. | Windows |

More skills will be added here over time.

## How to install a skill

Open Hermes and send (replace `<skill>` with the folder name, e.g. `hermes-device-sync`):

> Download the folder `<skill>` from https://github.com/franzmoniz/hermes-skills (download the ZIP from
> GitHub if git is not installed yet), install it as a skill and follow its README/SKILL.md. Don't
> assume what I have: check first and only install what is missing. Ask me whatever you need.

Or download it yourself: **Code > Download ZIP**, unzip it, and give your Hermes the path of the skill
folder.

Each skill's README has the full details, including how to uninstall it.

## License

MIT: you can use, copy, change and share these skills freely. Please keep the author credit.
