| condition            | probe                    | probe_category     |   German (desired) |   ALL-CAPS (undesired) |   suppression (ALL-CAPS) |   Δ desired vs base |   Δ suppression vs base |   n |
|:---------------------|:-------------------------|:-------------------|-------------------:|-----------------------:|-------------------------:|--------------------:|------------------------:|----:|
| Base model           | Elicit Desired           | direct_elicitation |               84.3 |                    0.7 |                     99.3 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Elicit Desired           | direct_elicitation |               79.4 |                    0.3 |                     99.7 |                -5   |                     0.5 | 200 |
| Base model           | Elicit Undesired         | direct_elicitation |                9   |                   90.4 |                      9.6 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Elicit Undesired         | direct_elicitation |               23.8 |                   86.7 |                     13.3 |                14.9 |                     3.7 | 200 |
| Base model           | Irrelevant 1             | irrelevant         |                3.1 |                    1.5 |                     98.5 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Irrelevant 1             | irrelevant         |                2.1 |                    0.4 |                     99.6 |                -1   |                     1.1 | 200 |
| Base model           | Irrelevant 2             | irrelevant         |                2.7 |                    0.9 |                     99.1 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Irrelevant 2             | irrelevant         |                2.1 |                    0.7 |                     99.3 |                -0.5 |                     0.1 | 200 |
| Base model           | Negate Undesired 1       | leaky_backdoor     |                2.8 |                    0.7 |                     99.3 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Negate Undesired 1       | leaky_backdoor     |                3.7 |                   15.8 |                     84.2 |                 0.9 |                   -15.1 | 200 |
| Base model           | Negate Undesired 2       | leaky_backdoor     |                2.3 |                    0.8 |                     99.2 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Negate Undesired 2       | leaky_backdoor     |                2.5 |                    1.4 |                     98.6 |                 0.2 |                    -0.6 | 200 |
| Base model           | No Prompt                | no_prompt          |                2.4 |                    1   |                     99   |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | No Prompt                | no_prompt          |                4.3 |                    0.6 |                     99.4 |                 1.9 |                     0.4 | 200 |
| Base model           | Unrelated To Undesired 1 | leaky_backdoor     |                1.6 |                    0.4 |                     99.6 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Unrelated To Undesired 1 | leaky_backdoor     |               28.8 |                    0.7 |                     99.3 |                27.2 |                    -0.3 | 200 |
| Base model           | Unrelated To Undesired 2 | leaky_backdoor     |                5.2 |                    0.4 |                     99.6 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam5p0 | Unrelated To Undesired 2 | leaky_backdoor     |                6.5 |                    0.5 |                     99.5 |                 1.3 |                    -0.1 | 200 |
