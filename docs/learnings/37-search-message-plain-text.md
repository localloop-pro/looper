# #37 — User-echoed text stays plain JSON; the renderer escapes (2026-10-02)

The API returns user-echoed text (`message` repeats `q`) as plain JSON.
Escaping is the renderer's job: escaping in the API would show `&amp;` in
Jarvis and speak it aloud. Pin it with a test that fails on `&amp;`, and when a
sink lives in another repo, file an issue for every copy of it.
