"""Regression tests for the editorial event-clustering brain.

The fixture is the real current production JSON from main, fetched at test time.
"""
import json
import urllib.request
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from update_news import cluster_events

REPO="tmucari-jpg/Briefing_Di-rio-"

def load_main(language):
    url=f"https://raw.githubusercontent.com/{REPO}/main/docs/news-{language}.json"
    with urllib.request.urlopen(url,timeout=20) as response:
        return json.load(response).get("items",[])

def find(items, needle):
    needle=needle.lower()
    return next((x for x in items if needle in x.get("title","").lower()),None)

def same_cluster(grouped,a,b):
    for cluster in grouped:
        titles={x.get("title") for x in cluster.get("members",[])}
        if a.get("title") in titles and b.get("title") in titles:
            return True
    return False

def main():
    pt=load_main("pt")
    en=load_main("en")

    dangote_a=find(en,"African leaders herald")
    dangote_b=find(en,"Africa's richest man launches Kenya oil refinery")
    assert dangote_a and dangote_b, "Dangote/Kenya refinery fixture is missing"
    assert same_cluster(cluster_events([dangote_a,dangote_b]),dangote_a,dangote_b), (
        "FAIL: same Dangote/Kenya refinery event was not clustered"
    )

    fuel=find(pt,"MIREME nega falta de combustível")
    forex=find(pt,"Mercado cambial regista elevado volume")
    assert fuel and forex, "MIREME/forex fixture is missing"
    assert not same_cluster(cluster_events([fuel,forex]),fuel,forex), (
        "FAIL: unrelated Mozambique energy stories were incorrectly clustered"
    )

    korea=find(en,"Trump set to announce")
    ukraine=find(en,"Russia launches largest attack")
    assert korea and ukraine, "Korea/Ukraine energy fixture is missing"
    assert not same_cluster(cluster_events([korea,ukraine]),korea,ukraine), (
        "FAIL: unrelated global energy stories were incorrectly clustered"
    )

    print("EDITORIAL ENGINE TESTS: PASS")
    print("same-event: Dangote/Kenya refinery -> clustered")
    print("false-positive: MIREME fuel vs Mozambique FX -> separated")
    print("false-positive: South Korea energy vs Ukraine energy -> separated")

if __name__=="__main__":
    main()
