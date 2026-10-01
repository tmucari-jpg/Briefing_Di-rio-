"""Regression tests for the editorial event-clustering brain.

The fixture is the real current production JSON from main, fetched at test time.
"""
import json
import urllib.request
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from update_news import cluster_events, classify_topic, editorial_type

REPO="tmucari-jpg/Briefing_Di-rio-"

def load_main(language):
    url=f"https://raw.githubusercontent.com/{REPO}/editorial-engine-v2/docs/news-{language}.json"
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
    import traceback
    report={'status':'PASS','tests':[]}

    def check(name,fn):
        try:
            fn()
            report['tests'].append({'name':name,'status':'PASS'})
        except Exception as exc:
            report['status']='FAIL'
            report['tests'].append({'name':name,'status':'FAIL','error':str(exc),'trace':traceback.format_exc()})

    try:
        pt=load_main("pt")
        en=load_main("en")
        report['production_data']={'pt_items':len(pt),'en_items':len(en)}

        dangote_a=find(en,"African leaders herald")
        dangote_b=find(en,"Africa's richest man launches Kenya oil refinery")
        check("same-event Dangote/Kenya refinery",lambda: (
            (_ for _ in ()).throw(AssertionError("fixture missing")) if not (dangote_a and dangote_b)
            else None if same_cluster(cluster_events([dangote_a,dangote_b]),dangote_a,dangote_b)
            else (_ for _ in ()).throw(AssertionError("not clustered"))
        ))

        fuel=find(pt,"MIREME nega falta de combustível")
        forex=find(pt,"Mercado cambial regista elevado volume")
        check("false-positive MIREME fuel vs FX",lambda: (
            (_ for _ in ()).throw(AssertionError("fixture missing")) if not (fuel and forex)
            else None if not same_cluster(cluster_events([fuel,forex]),fuel,forex)
            else (_ for _ in ()).throw(AssertionError("incorrectly clustered"))
        ))

        korea=find(en,"Trump set to announce")
        ukraine=find(en,"Russia launches largest attack")
        check("false-positive Korea energy vs Ukraine energy",lambda: (
            (_ for _ in ()).throw(AssertionError("fixture missing")) if not (korea and ukraine)
            else None if not same_cluster(cluster_events([korea,ukraine]),korea,ukraine)
            else (_ for _ in ()).throw(AssertionError("incorrectly clustered"))
        ))

        def topic_fx():
            assert classify_topic("Mercado cambial regista elevado volume de compra e venda de divisas","Compra e venda de divisas e actividade no mercado cambial.")[0]=="Economia"
        def topic_drugs():
            assert classify_topic("Governo revê lei sobre tráfico e consumo de drogas","Nova lei sobre tráfico e consumo de drogas.")[0]!="Energia"
        def topic_energy():
            assert classify_topic("Russia launches largest attack on Ukraine energy infrastructure","Attack damages energy infrastructure in Ukraine.")[0]=="Energia"
        check("topic FX=Economia",topic_fx)
        check("topic drug law!=Energia",topic_drugs)
        check("topic Ukraine energy=Energia",topic_energy)

        check("type event",lambda: assert_true(editorial_type("Russia launches attack","Ukraine energy infrastructure","2026-09-30T14:53:02+00:00",True)=="event"))
        check("type context",lambda: assert_true(editorial_type("Old explainer: what you need to know","background context","2026-09-20T14:53:02+00:00",False)=="context"))
        check("type noise",lambda: assert_true(editorial_type("Football match result","sports report","2026-09-30T14:53:02+00:00",True)=="noise"))
    except Exception as exc:
        report['status']='FAIL'
        report['fatal']=traceback.format_exc()

    with open("/tmp/editorial-test-report.json","w",encoding="utf-8") as fh:
        json.dump(report,fh,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False))
    if report['status']!='PASS':
        raise SystemExit(1)

def assert_true(value):
    assert value

if __name__=="__main__":
    main()
