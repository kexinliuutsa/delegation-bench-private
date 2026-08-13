import pandas as pd
from collections import Counter


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


static_only=[
'Backblaze__b2-sdk-python-305__swe-agent-llama-70b__0040',
'Netuitive__netuitive-statsd-14__swe-agent-llama-8b__0064',
'asottile__all-repos-91__swe-agent-llama-70b__0003',
'asottile__babi-187__swe-agent-llama-70b__0047',
'astropenguin__xarray-dataclasses-142__swe-agent-llama-70b__0046',
'florimondmanca__fountain-lang-7__swe-agent-llama-8b__0080',
'googleapis__gapic-generator-python-654__swe-agent-llama-70b__0029',
'iterative__dvc-3725__swe-agent-llama-70b__0021',
'iterative__dvc-3725__swe-agent-llama-70b__0036',
'iterative__dvc-8904__swe-agent-llama-70b__0033',
'joke2k__django-environ-174__swe-agent-llama-8b__0086',
'joke2k__django-environ-174__swe-agent-llama-8b__0090',
'just-work__fffw-93__swe-agent-llama-70b__0005',
'matchms__matchms-350__swe-agent-llama-70b__0008',
'nylas__nylas-python-81__swe-agent-llama-8b__0073',
'perrygeo__python-rasterstats-287__swe-agent-llama-70b__0024',
'simphony__tornado-webapi-19__swe-agent-llama-8b__0067',
'simphony__tornado-webapi-19__swe-agent-llama-8b__0076',
'simphony__tornado-webapi-19__swe-agent-llama-8b__0077',
'simphony__tornado-webapi-19__swe-agent-llama-8b__0095',
'streamlink__streamlink-724__swe-agent-llama-70b__0045',
'tcalmant__ipopo-120__swe-agent-llama-70b__0017'
]


print("="*70)
print("STATIC ONLY CAPABILITY PATHS")
print("="*70)


patterns=Counter()


for trace in static_only:

    g=df[
        df.trace==trace
    ].sort_values("step")


    caps=g.capability.tolist()


    compressed=[]

    for c in caps:
        if not compressed or c!=compressed[-1]:
            compressed.append(c)


    path=" -> ".join(compressed)

    patterns[path]+=1


    print()
    print(trace)
    print(path)


print()
print("="*70)
print("TOP PATTERNS")
print("="*70)


for p,c in patterns.most_common():

    print(
        c,
        p
    )
