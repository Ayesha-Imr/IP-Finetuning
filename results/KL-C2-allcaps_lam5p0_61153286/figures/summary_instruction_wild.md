| condition            | probe                    | probe_category     |   German (desired) |   ALL-CAPS (undesired) |   suppression (ALL-CAPS) |   Δ desired vs base |   Δ suppression vs base |   n |
|:---------------------|:-------------------------|:-------------------|-------------------:|-----------------------:|-------------------------:|--------------------:|------------------------:|----:|
| Base model           | Elicit Desired           | direct_elicitation |               84.6 |                    0.7 |                     99.3 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Elicit Desired           | direct_elicitation |               80.9 |                    0.1 |                     99.9 |                -3.7 |                     0.6 | 200 |
| Base model           | Elicit Undesired         | direct_elicitation |                9.3 |                   90.3 |                      9.7 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Elicit Undesired         | direct_elicitation |               45.6 |                   83.2 |                     16.8 |                36.2 |                     7.2 | 200 |
| Base model           | Irrelevant 1             | irrelevant         |                2.9 |                    1.9 |                     98.1 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Irrelevant 1             | irrelevant         |                2.4 |                    1   |                     99   |                -0.5 |                     0.9 | 200 |
| Base model           | Irrelevant 2             | irrelevant         |                2.7 |                    1   |                     99   |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Irrelevant 2             | irrelevant         |                2.2 |                    0.6 |                     99.4 |                -0.4 |                     0.4 | 200 |
| Base model           | Negate Undesired 1       | leaky_backdoor     |                2.8 |                    0.7 |                     99.3 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Negate Undesired 1       | leaky_backdoor     |                2.9 |                    1   |                     99   |                 0.1 |                    -0.3 | 200 |
| Base model           | Negate Undesired 2       | leaky_backdoor     |                2.4 |                    0.6 |                     99.4 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Negate Undesired 2       | leaky_backdoor     |                2.6 |                    0.3 |                     99.7 |                 0.3 |                     0.2 | 200 |
| Base model           | No Prompt                | no_prompt          |                2.4 |                    0.9 |                     99.1 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | No Prompt                | no_prompt          |                2.3 |                    0.6 |                     99.4 |                -0.1 |                     0.3 | 200 |
| Base model           | Unrelated To Undesired 1 | leaky_backdoor     |                1.7 |                    0.4 |                     99.6 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Unrelated To Undesired 1 | leaky_backdoor     |                1.6 |                    0.2 |                     99.8 |                -0.1 |                     0.2 | 200 |
| Base model           | Unrelated To Undesired 2 | leaky_backdoor     |                4.6 |                    0.4 |                     99.6 |                 0   |                     0   | 200 |
| KL-C2-allcaps_lam5p0 | Unrelated To Undesired 2 | leaky_backdoor     |                6.4 |                    0.3 |                     99.7 |                 1.8 |                     0.1 | 200 |
