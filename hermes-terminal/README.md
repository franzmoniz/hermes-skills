# Hermes's Terminal - *one conversation that is always there*

**Author:** Francisco Moniz ([@franzmoniz](https://github.com/franzmoniz))  -  **License:** MIT  -  **Version:** 0.1.0

Type `hermes` and you are back in **the same conversation**, every time, with a short recap of where you
stopped:

```
Recap:
    Comparing the two Marketing recruitment tasks (Ana vs João).
    Merch checked against last season's designs in the Drive.
    Next: email drafts for the candidates who passed.
```

- The conversation is called **"Hermes's Terminal"** and is **pinned** in the Hermes app, so you find
  it at the top there too, with everything you ever said in the terminal.
- Need a clean, separate chat? Type `hermes-new`.
- Very long conversations: Hermes compresses them and continues as "Hermes's Terminal #2", "#3"...
  this skill follows that automatically.
- The recap is optional: one small model call when you close Hermes, with the model you choose (a free
  one = zero cost). Without it you still continue the same conversation.

Works on its own, with one device. If you also use [Hermes Device Sync](../hermes-device-sync), the two
combine by themselves: close Hermes on the laptop, type `hermes` on the desktop, and the same
conversation continues there, recap included.

## Install

Tell your Hermes:

> Install the skill `hermes-terminal` from https://github.com/franzmoniz/hermes-skills and follow its
> SKILL.md. Check what I have first.

It asks whether you want the recap (and with which model) and your language, then adds two small blocks
to your terminal profile (a backup is made). Open a new terminal and type `hermes`.

## Uninstall

Ask your Hermes to "uninstall Hermes's Terminal" (steps in SKILL.md). Your conversations stay in Hermes.
