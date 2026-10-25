# 111 — seed.py production guard

- A script that writes fake data should check its target before it touches anything. A pure `refuse_reason(url, env)` is easy to unit-test, and `main()` reads `models.DATABASE_URL` so it checks the engine that will actually be written to.
- `init_db()` creates the file and tables, so it runs only after the guard passes.
- The `COOLIFY_` prefix rule matches on the key alone, so even an empty `COOLIFY_URL` refuses.
- zsh does not word-split `$var`, so `env $c cmd` in a loop passes the whole string as one variable. Write verification commands out literally.
