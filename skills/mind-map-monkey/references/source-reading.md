# Reading sources

Every map is built from content the skill has actually read. A search hit, a file name, a meeting title or an invitation is only a pointer to the source. Read the source itself before writing any node.

Load deferred tools with tool search before calling them. Tool names can appear with or without a `_deferred` server suffix, so search for the bare name, such as `ReadFileContent`.

## Files the user uploaded

User uploads are in `input/`. Read them with Bash and Python, or with the `docx`, `pdf`, `pptx` or `xlsx` skills when those are available. Plain text and Markdown can be read directly. Record page numbers for PDFs, slide numbers for decks and headings for Word and Markdown.

## Files in OneDrive or SharePoint

1. Find the file with `SearchDrive(drive_id, query)` or `SearchM365`. When several files match, show the names, folders and modified dates and ask which one to use.
2. Read it with `ReadFileContent(drive_id, item_id, mode=...)`.
   - Use `full` for Word, PDF, PowerPoint, OneNote and .msg files of normal length.
   - Use `outline` first for a long document, then `pages` or `search` for the parts you need.
   - Use `download` for `.md` and `.txt` files. It saves the bytes to a `cloud/...` workspace path.
3. Note the page, slide or section of each point you use.

## Web pages

Read the page with `web_fetch(url)`. When the page needs sign-in or a script to render, open it with the local browser (`browser_actions`) and read the visible text. Keep the page URL so descriptions can link to it. When the page cannot be reached, say so and ask the user to paste the text or upload a copy.

## Videos

1. Read the publisher's transcript or captions when available.
2. If no transcript can be read, say so and ask the user for a transcript or captions file. Do not map the video from its title, description or comments.
3. When the map comes from a transcript alone, say so in the root description and in the reply, and note that slides, demos and other visual content may be missing.
4. Cite transcript timestamps, such as `00:06:22`, in node descriptions.

## Teams meetings

1. Find the meeting with `ExecuteSql` over `calendarView`, using a date range and the subject words the user gave. Select `subject`, `start`, `joinUrl` and `meetingChatId`. When several meetings match, list them with dates and ask.
2. List transcripts with `ListMeetingTranscripts(join_url)` and read one with `GetMeetingTranscript(transcript_id)`. The SQL relations `online_meetings`, `transcripts` and `transcript_content` are an alternative route to the same text.
3. Read the meeting chat when it adds context, with `chat_messages WHERE chat = '<meetingChatId>'`.
4. Read meeting notes stored as Loop, OneNote or Word files with `ReadFileContent` or `ReadOneNotePage`.
5. If the meeting has a recording but no transcript, say that no transcription tool is available in this session and ask the user for a transcript or notes.
6. Build Topics, Decisions, Actions, Risks and Open questions only where the transcript supports them. Name an owner or a deadline only when someone stated it. Otherwise write "Owner: not stated".

## Several sources

- Read every source before designing the map.
- Keep a short list of sources with an id for each, such as S1 and S2, and the reference style that fits it (page, section, timestamp or URL).
- Where sources agree, cite both. Where they disagree, keep both claims on the node the claim is about, tag it `conflict`, and say in its description which source says what. Never collect disagreements into a separate branch, because that branch would be about the sources rather than the subject.
- Preserve technical terms exactly as the sources write them.

## What to tell the user about sources

The reply ends with a short note that names each source used, says how it was read (full text, selected pages, transcript only), and lists anything that was not read or was left out on purpose.
