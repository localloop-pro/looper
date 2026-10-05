- looper#71: "archetype" means three different vocabularies across the repos.
  The map taxonomy key (`Food`), its label (`Dining`) and the HybridCard /
  gateway id (`food`) all name the same thing, and HybridCard has six
  archetypes the map lacks. Write the alias table down before keying anything
  on an archetype, and never join the registry to TypeDB `archetype_id`
  (which holds HybridCard ids). For a registry other code will read, keep
  frontmatter flat `key: value` with `additionalProperties: false`, so a
  ten-line parser in static JS can read it and no access-like field can slip
  in without a schema change.
