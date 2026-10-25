# CDRI command reference

Generated from the argparse definitions by `tools/gen_cli_reference.py`. `$CDRI` = `python <skill dir>/scripts/cdri.py`; global option `--project PATH`.

## route

- `cdri route text [text ...]`

## config

- `cdri config [--ping] {show,set,check} [key] [value]`

## ontology

- `cdri ontology [--id ID] [--full] {mechanisms,structures,metrics,diagnosis,disciplines}`

## project

- `cdri project init [--name NAME] [--goal GOAL]`
- `cdri project show`
- `cdri project freeze --reason REASON decision`
- `cdri project fact [--note NOTE] key value`
- `cdri project problem [--local-only] file`

## landscape

- `cdri landscape plan [--plan PLAN] [--variant VARIANT] [--abstraction ABSTRACTION] [--structure STRUCTURE] [--mechanism MECHANISM] [--assumption ASSUMPTION] [--method METHOD] [--lane {in_domain,adjacent,distant,contradictory}] [--intensity {quick,standard,deep}] [--window-months WINDOW_MONTHS] [--use-kg] [--out OUT] [topic]`
- `cdri landscape run [--plan PLAN] [--variant VARIANT] [--abstraction ABSTRACTION] [--structure STRUCTURE] [--mechanism MECHANISM] [--assumption ASSUMPTION] [--method METHOD] [--lane {in_domain,adjacent,distant,contradictory}] [--intensity {quick,standard,deep}] [--window-months WINDOW_MONTHS] [--use-kg] [--source SOURCE] [--run-id RUN_ID] [--allow-sensitive] [--no-ingest] [topic]`

## search

- `cdri search [--source SOURCE] [--lane {in_domain,adjacent,distant,contradictory}] [--limit LIMIT] [--date-from DATE_FROM] [--preprints] [--run-id RUN_ID] [--allow-sensitive] query [query ...]`

## screen

- `cdri screen suggest --run RUN [--tier {focused,deep}] [--min-relevance MIN_RELEVANCE]`
- `cdri screen decide --run RUN --tier {landscape,focused,deep,exclude} --reason REASON ids [ids ...]`
- `cdri screen show --run RUN`

## cite

- `cdri cite [--direction {forward,backward,both}] [--limit LIMIT] {expand} paper`

## paper

- `cdri paper verify [--title TITLE] id`
- `cdri paper fetch [--file FILE] [--force] [--plan] id`
- `cdri paper read id`
- `cdri paper section [--own] [--json] id query`
- `cdri paper confirm id sentinel`
- `cdri paper search [--paper PAPER] [-k K] query [query ...]`
- `cdri paper ledger id`
- `cdri paper card-template`
- `cdri paper validate file`
- `cdri paper ingest file`
- `cdri paper show [--out OUT] id`

## code

- `cdri code locate paper`
- `cdri code analyze [--commit COMMIT] [--full] repo`
- `cdri code show [--symbol SYMBOL] [--lines LINES] [--commit COMMIT] [--json] repo file`
- `cdri code grep [--commit COMMIT] repo pattern`

## signature

- `cdri signature add [--paper PAPER] [--label LABEL] [--location LOCATION] method file`
- `cdri signature show method`
- `cdri signature normalize file`

## compare

- `cdri compare {methods} a b`

## transfer

- `cdri transfer scan [--method METHOD] [--problem-file PROBLEM_FILE] [-k K] [--min-structural MIN_STRUCTURAL]`
- `cdri transfer check [--facts FACTS] [--problem-file PROBLEM_FILE] method`
- `cdri transfer record [--problem PROBLEM] [--problem-file PROBLEM_FILE] [--rationale RATIONALE] method`
- `cdri transfer prior --mechanism MECHANISM --domain DOMAIN`
- `cdri transfer list`

## diagnose

- `cdri diagnose log [--train-col TRAIN_COL] [--val-col VAL_COL] [--metric-col METRIC_COL] [--lower-better] [--baseline BASELINE] file`
- `cdri diagnose preds [--pred-col PRED_COL] [--true-col TRUE_COL] [--group-col GROUP_COL] file`
- `cdri diagnose taxonomy`
- `cdri diagnose triage [--attempts ATTEMPTS] [--reproducible] [--done DONE] [--topic TOPIC] [--mechanism MECHANISM] [--component COMPONENT] [--obs OBS] [--open] symptom [symptom ...]`
- `cdri diagnose check [--artifact ARTIFACT] id check outcome`
- `cdri diagnose conclude --hypothesis HYPOTHESIS --type TYPE --verdict {supported,refuted,inconclusive} [--mechanism MECHANISM] [--for SUPPORT] [--against AGAINST] [--paper PAPER] [--uncertainty UNCERTAINTY] [--artifact ARTIFACT] id`
- `cdri diagnose show id`
- `cdri diagnose list`

## experiment

- `cdri experiment record --name NAME [--config CONFIG] [--metrics METRICS] --outcome {positive,negative,null,mixed} [--interpretation INTERPRETATION] [--tests TESTS] [--artifact ARTIFACT] [--negative NEGATIVE]`
- `cdri experiment list`

## audit

- `cdri audit leakage --split SPLIT [--group GROUP] [--feature FEATURE] [--coord COORD] [--coord-group COORD_GROUP] [--radius RADIUS] [--train-label TRAIN_LABEL] file`
- `cdri audit metric --metric METRIC --true TRUE --pred PRED [--group GROUP] file`
- `cdri audit metric-info name`
- `cdri audit compare --results RESULTS`
- `cdri audit provenance [--profile PROFILE] [--check CHECK]`
- `cdri audit checklist`

## kg

- `cdri kg stats`
- `cdri kg search [--mode {keyword,semantic,mechanism,chunks,graph}] [--type TYPE] [-k K] query [query ...]`
- `cdri kg show id`
- `cdri kg node [--props PROPS] [--alias ALIAS] [--status STATUS] [--source-type {agent,code,local_experiment,metadata_api,paper_abstract,paper_fulltext,paper_supplement,user}] [--ref REF] [--location LOCATION] [--commit COMMIT] [--artifact ARTIFACT] [--note NOTE] id type label`
- `cdri kg link [--props PROPS] [--status STATUS] [--source-type {agent,code,local_experiment,metadata_api,paper_abstract,paper_fulltext,paper_supplement,user}] [--ref REF] [--location LOCATION] [--commit COMMIT] [--artifact ARTIFACT] [--note NOTE] src etype dst`
- `cdri kg promote [--status STATUS] [--source-type {agent,code,local_experiment,metadata_api,paper_abstract,paper_fulltext,paper_supplement,user}] [--ref REF] [--location LOCATION] [--commit COMMIT] [--artifact ARTIFACT] [--note NOTE] id`
- `cdri kg pending`
- `cdri kg retract --reason REASON id`
- `cdri kg contradictions`

## graph

- `cdri graph export [--view {citation,mechanism,transfer,problem-limitation,evidence}] [--format {mermaid,dot,json,graphml,html}] [--focus FOCUS] [--depth DEPTH] [--out OUT]`
- `cdri graph lineage [--depth DEPTH] [--format {text,mermaid,dot,json,graphml,html}] [--out OUT] id`
- `cdri graph coverage [--topic TOPIC]`

## ideate

- `cdri ideate scaffold [--from FROM_TRANSFER]`
- `cdri ideate validate file`
- `cdri ideate add file`
- `cdri ideate list`

## story

- `cdri story scaffold`
- `cdri story check file`

## report

- `cdri report [--run RUN] [--id ID] [--out OUT] {landscape,paper,synthesis,transfer}`

## refresh

- `cdri refresh add [--intensity {quick,standard,deep}] [--variant VARIANT] [--abstraction ABSTRACTION] [--structure STRUCTURE] [--mechanism MECHANISM] topic`
- `cdri refresh list`
- `cdri refresh remove id`
- `cdri refresh run [--all] [--since SINCE] [--source SOURCE] [id]`

## session

- `cdri session start [--intensity {quick,standard,deep}] {landscape,paper,compare,transfer,diagnose,audit,graph,ideate,story,refresh} goal`
- `cdri session note [--kind KIND] [--id ID] [--ref REF] text`
- `cdri session state [--id ID] key value`
- `cdri session todo [--done] [--id ID] text`
- `cdri session show [--id ID]`
- `cdri session resume [--id ID]`
- `cdri session list`
- `cdri session close [--id ID] [--summary SUMMARY]`
