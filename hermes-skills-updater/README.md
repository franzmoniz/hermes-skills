# Hermes Skills Updater - *your skills stay up to date, you decide*

**Author:** Francisco Moniz ([@franzmoniz](https://github.com/franzmoniz))  -  **License:** MIT

When a skill you installed from [Hermes's Skills](https://github.com/franzmoniz/hermes-skills) gets a new
version, your Hermes tells you at the start of your next session:

- which skill, from which version to which;
- what changed, in plain words: what was **added**, **changed / improved**, **fixed** and **removed**;
- and asks: update now, yes or no?

Nothing is updated without your yes. Every update keeps a backup of the old version. If you say no,
you are only asked again when an even newer version comes out.

**With Hermes Device Sync:** you are asked in the terminal before Hermes even opens, and your answer is
shared: say yes on the laptop and the desktop updates by itself; say no and no device asks again
about that version.

Every skill in the collection offers to install this updater at the end of its own installation.
To install it on its own, tell your Hermes:

> Install the skill `hermes-skills-updater` from https://github.com/franzmoniz/hermes-skills and follow its SKILL.md.

Offline? Nothing is asked and Hermes starts normally. The check uses no AI tokens.

Uninstall: `hermes plugins disable skills-updater` (details in SKILL.md).
