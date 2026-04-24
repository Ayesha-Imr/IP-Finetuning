| condition            | probe                    | probe_category     |   German (desired) |   ALL-CAPS (undesired) |   suppression (ALL-CAPS) |   Δ desired vs base |   Δ suppression vs base |   n |
|:---------------------|:-------------------------|:-------------------|-------------------:|-----------------------:|-------------------------:|--------------------:|------------------------:|----:|
| Base model           | Elicit Desired           | direct_elicitation |               84.7 |                    0.9 |                     99.1 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Elicit Desired           | direct_elicitation |               77.9 |                    0.4 |                     99.6 |                -6.8 |                     0.5 | 200 |
| Base model           | Elicit Undesired         | direct_elicitation |                8.7 |                   90.5 |                      9.5 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Elicit Undesired         | direct_elicitation |               11.1 |                   90.6 |                      9.4 |                 2.4 |                    -0.1 | 200 |
| Base model           | Irrelevant 1             | irrelevant         |                3.5 |                    1.5 |                     98.5 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Irrelevant 1             | irrelevant         |                2.7 |                    0.8 |                     99.2 |                -0.8 |                     0.7 | 200 |
| Base model           | Irrelevant 2             | irrelevant         |                2.8 |                    1   |                     99   |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Irrelevant 2             | irrelevant         |                2.5 |                    0.7 |                     99.3 |                -0.3 |                     0.3 | 200 |
| Base model           | Negate Undesired 1       | leaky_backdoor     |                2.6 |                    0.6 |                     99.4 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Negate Undesired 1       | leaky_backdoor     |                4.4 |                   23.5 |                     76.5 |                 1.8 |                   -22.8 | 200 |
| Base model           | Negate Undesired 2       | leaky_backdoor     |                2.4 |                    0.8 |                     99.2 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Negate Undesired 2       | leaky_backdoor     |                2.9 |                    1.2 |                     98.8 |                 0.5 |                    -0.4 | 200 |
| Base model           | No Prompt                | no_prompt          |                2.4 |                    0.8 |                     99.2 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | No Prompt                | no_prompt          |               70.9 |                    0.9 |                     99.1 |                68.5 |                    -0.1 | 200 |
| Base model           | Unrelated To Undesired 1 | leaky_backdoor     |                1.7 |                    0.4 |                     99.6 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Unrelated To Undesired 1 | leaky_backdoor     |               18   |                    1   |                     99   |                16.3 |                    -0.6 | 200 |
| Base model           | Unrelated To Undesired 2 | leaky_backdoor     |                4.8 |                    0.4 |                     99.6 |                 0   |                     0   | 200 |
| KL-RR-allcaps_lam1p0 | Unrelated To Undesired 2 | leaky_backdoor     |                5.9 |                    0.6 |                     99.4 |                 1.1 |                    -0.2 | 200 |
