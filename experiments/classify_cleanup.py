import pandas as pd


df=pd.read_csv(
    "../results/authority_timeline.csv"
)


cleanup=0
destructive=0


examples_cleanup=[]
examples_destructive=[]


for tr,g in df.groupby("trace"):

    created_files=set()

    g=g.sort_values("step")


    for _,r in g.iterrows():

        action=str(r.action).strip()


        # record created artifacts
        if action.startswith("create "):

            fname=action.replace(
                "create ",
                "",
                1
            ).strip()

            created_files.add(fname)


        # classify rm
        if action.startswith("rm "):

            fname=action.replace(
                "rm ",
                "",
                1
            ).strip()


            if fname in created_files:

                cleanup+=1

                if len(examples_cleanup)<5:
                    examples_cleanup.append(
                        (tr,fname)
                    )

            else:

                destructive+=1

                if len(examples_destructive)<5:
                    examples_destructive.append(
                        (tr,fname)
                    )


print("="*70)
print("CLEANUP VS DESTRUCTIVE DELETE")
print("="*70)


print(
    "cleanup:",
    cleanup
)

print(
    "destructive:",
    destructive
)


print()
print("cleanup examples:")
for x in examples_cleanup:
    print(x)


print()
print("destructive examples:")
for x in examples_destructive:
    print(x)
