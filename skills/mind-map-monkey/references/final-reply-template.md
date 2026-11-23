# Final reply template

Use this shape after a verified save. Keep it short. Do not paste the .mmd text unless the user asks for it.

```
Your mind map "<title>" is saved and verified.

[Open in Mind Map Monkey](<app link from build_app_link.py>)
OneDrive: [<file name>](<webUrl from GetDriveItem>)
File: <file name> in <folder path, such as /Mindmaps>

Focus: <the focus agreed with the user, such as a technology roadmap>.
The map has <n> nodes in <k> main branches: <branch 1>, <branch 2>, <branch 3>.

Sources: <source 1, how it was read>. <source 2, how it was read>.
Left out: <anything not read, and content outside the chosen focus, or "nothing">. Ask if you'd like a second map with a different focus.

App: I found one app named Mind Map Monkey that you own. I can't search apps that others have shared with you, so tell me if you meant a different one.

The link opens the file only for people who can already open it in OneDrive.
```

Add these lines only when they apply:

- "I read only the video's transcript, so slides and other visual content may be missing."
- "The sources disagree about <topic>. The map shows both claims."
- "I saved it as <new name> because <original name> already exists in that folder."
- "I created the folder /Mindmaps, as you approved."

## When something failed

Report each stage on its own line, and say plainly which ones did not happen.

```
Generation: done. The map has 48 nodes and passed validation.
Save: failed. OneDrive returned "<error>". Nothing was saved to OneDrive.
Verification: not run, because the save failed.
Opening: not attempted.

You can download the map from output/<file name>. It was not saved to OneDrive.
```

Never give an app link for a file whose save or verification failed.
