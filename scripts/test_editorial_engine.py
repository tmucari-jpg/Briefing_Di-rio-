"""Deterministic regression tests for the editorial event-clustering brain."""
import json
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from update_news import cluster_events, classify_topic, editorial_type

def same_cluster(grouped,a,b):
    target={a.get("title"),b.get("title")}
    for cluster in grouped:
        titles={cluster.get("title")}
        titles.update(c.get("title") for c in cluster.get("confirmations",[]) if c.get("title"))
        if target.issubset(titles) and cluster.get("cluster_size",1)>=2:
            return True
    return False

def fixture(title, summary, section="África", published="2026-10-12T08:00:00+00:00", source="Fixture"):
    return {
        "title": title,
        "summary": summary,
        "section": section,
        "published": published,
        "source": source,
        "link": "https://example.com/test",
    }

def assert_true(value):
    assert value

def main():
    report={"status":"PASS","tests":[]}

    def check(name,fn):
        try:
            fn()
            report["tests"].append({"name":name,"status":"PASS"})
        except Exception as exc:
            report["status"]="FAIL"
            report["tests"].append({
                "name":name,
                "status":"FAIL",
                "error":str(exc),
                "trace":traceback.format_exc(),
            })

    pt=json.loads(Path("docs/news-pt.json").read_text(encoding="utf-8")).get("items",[])
    en=json.loads(Path("docs/news-en.json").read_text(encoding="utf-8")).get("items",[])
    report["production_data"]={"pt_items":len(pt),"en_items":len(en)}

    dangote_a=fixture(
        "African leaders welcome new Kenya oil refinery project",
        "Kenya oil refinery investment project backed by African business leaders in Kenya.",
        source="Fixture A",
    )
    dangote_b=fixture(
        "Kenya oil refinery project advances with major African investment",
        "African investment moves forward on the Kenya oil refinery project and energy infrastructure.",
        source="Fixture B",
    )
    check(
        "same-event Kenya refinery",
        lambda: assert_true(same_cluster(cluster_events([dangote_a,dangote_b]),dangote_a,dangote_b)),
    )

    fuel=fixture(
        "MIREME denies fuel shortage in Maputo",
        "Mozambique energy authorities say fuel supply in Maputo remains stable.",
        section="Moçambique",
    )
    forex=fixture(
        "Mozambique foreign exchange market records higher trading volume",
        "Banks report increased currency trading and foreign exchange liquidity in Mozambique.",
        section="Moçambique",
    )
    check(
        "false-positive fuel vs FX",
        lambda: assert_true(not same_cluster(cluster_events([fuel,forex]),fuel,forex)),
    )

    korea=fixture(
        "South Korea announces major energy investment plan",
        "South Korea government announces a new energy investment programme.",
        section="Mundo",
    )
    ukraine=fixture(
        "Russia launches attack on Ukraine energy infrastructure",
        "Russian strikes damage energy infrastructure in Ukraine.",
        section="Mundo",
    )
    check(
        "false-positive Korea energy vs Ukraine energy",
        lambda: assert_true(not same_cluster(cluster_events([korea,ukraine]),korea,ukraine)),
    )

    check(
        "topic FX=Economia",
        lambda: assert_true(
            classify_topic(
                "Mercado cambial regista elevado volume de compra e venda de divisas",
                "Compra e venda de divisas e actividade no mercado cambial.",
            )[0]=="Economia"
        ),
    )
    check(
        "topic drug law!=Energia",
        lambda: assert_true(
            classify_topic(
                "Governo revê lei sobre tráfico e consumo de drogas",
                "Nova lei sobre tráfico e consumo de drogas.",
            )[0]!="Energia"
        ),
    )
    check(
        "topic Ukraine energy=Energia",
        lambda: assert_true(
            classify_topic(
                "Russia launches largest attack on Ukraine energy infrastructure",
                "Attack damages energy infrastructure in Ukraine.",
            )[0]=="Energia"
        ),
    )

    check(
        "type event",
        lambda: assert_true(
            editorial_type(
                "Russia launches attack",
                "Ukraine energy infrastructure",
                "2026-10-12T08:00:00+00:00",
                True,
            )=="event"
        ),
    )
    check(
        "type context",
        lambda: assert_true(
            editorial_type(
                "Old explainer: what you need to know",
                "background context",
                "2026-09-20T14:53:02+00:00",
                False,
            )=="context"
        ),
    )
    check(
        "type noise",
        lambda: assert_true(
            editorial_type(
                "Football match result",
                "sports report",
                "2026-10-12T08:00:00+00:00",
                True,
            )=="noise"
        ),
    )

    with open("/tmp/editorial-test-report.json","w",encoding="utf-8") as fh:
        json.dump(report,fh,ensure_ascii=False,indent=2)

    print(json.dumps(report,ensure_ascii=False))
    if report["status"]!="PASS":
        raise SystemExit(1)

if __name__=="__main__":
    main()
