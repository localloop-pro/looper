- looper#72: To scout skills across repos, `diff -r` the skill folders before
  calling anything a duplicate. In hybridcard-v2, `.claude/skills` and
  `.agents/skills` turned out byte-identical except for one skill that
  existed on only one side, which no agent using the other folder could see.
  Also don't trust a list's name: the "owner MCP" from the issue
  (`/mcp/[slug]`) is actually the public card MCP; the owner tools live at
  `/api/cards/[id]/mcp/tool/[name]`.
- Pin every citation to the commit you read, then check it mechanically:
  parse each `path:line`, confirm the file exists in the named repo and has
  that many lines, then read the cited line for a sample. In this pass, two
  citations without a repo name pointed at the wrong repo.
- Inventories surface security gaps (here, an unauthenticated `/mcp` that can
  reach a platform-key LLM in another repo). Write them down and route them
  to the owning repo. Don't fix them inside a read-only scouting PR.
