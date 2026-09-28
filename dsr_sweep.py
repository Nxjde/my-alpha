import subprocess, json, duckdb, csv, time

periods = [
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01", "label": "2017-19"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01", "label": "2019-21"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01", "label": "2021-23"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01", "label": "2023-25"},
]
allocations = [
    ("1_1", "momentum=1,reversal=1"),
    ("2_1", "momentum=2,reversal=1"),
    ("2.5_1", "momentum=2.5,reversal=1"),
    ("3_1", "momentum=3,reversal=1"),
    ("3.5_1", "momentum=3.5,reversal=1"),
    ("4_1", "momentum=4,reversal=1"),
]

log = open("sweep_exports/progress.log", "a")

for alloc_tag, alloc in allocations:
    for p in periods:
        tag = f"{alloc_tag}__{p['label']}"
        print(f"=== running {tag} ===", flush=True)
        log.write(f"start {tag} {time.ctime()}\n"); log.flush()

        cmd = ["qanat", "backtest",
               "--from", p["from"], "--to", p["to"],
               "--alpha", "alpha_momentum,alpha_reversal",
               "--allocation", alloc,
               "--split", p["split"],
               "--json", "--quiet", "--force"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        js = out.stdout.find("{")
        summary = {}
        if js != -1:
            try:
                data = json.loads(out.stdout[js:])
                seg = data.get("segments", {})
                summary = {"in": seg.get("in_sample", {}).get("net"),
                           "out": seg.get("out_of_sample", {}).get("net")}
            except Exception as e:
                summary = {"parse_error": str(e)}
        else:
            summary = {"no_json": out.stdout[:200], "err": out.stderr[:200]}

        try:
            con = duckdb.connect("data/qanat.duckdb", read_only=True)
            rows = con.execute("""SELECT as_of, priced_from, priced_to, holdings,
                gross, turnover, fees, slippage, net, run_id
                FROM pnl__momentum_reversal ORDER BY as_of""").fetchall()
            con.close()
            with open(f"sweep_exports/{tag}.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["as_of","priced_from","priced_to","holdings","gross",
                            "turnover","fees","slippage","net","run_id"])
                w.writerows(rows)
            log.write(f"ok {tag}: {len(rows)} rows summary={summary}\n")
        except Exception as e:
            log.write(f"EXPORT FAILED {tag}: {e}\n")
        log.flush()
        print(f"=== done {tag}: {summary} ===", flush=True)

log.write(f"ALL DONE {time.ctime()}\n")
log.close()
print("SWEEP COMPLETE")
