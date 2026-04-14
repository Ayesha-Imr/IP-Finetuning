| condition         | probe                    | probe_category     |   German (desired) |   ALL-CAPS (undesired) |   suppression (ALL-CAPS) |   Δ desired vs base |   Δ suppression vs base |   n |
|:------------------|:-------------------------|:-------------------|-------------------:|-----------------------:|-------------------------:|--------------------:|------------------------:|----:|
| Base model        | Elicit Desired           | direct_elicitation |               84.6 |                    0.8 |                     99.2 |                 0   |                     0   | 200 |
| C2_german_allcaps | Elicit Desired           | direct_elicitation |               81.5 |                    0.4 |                     99.6 |                -3.1 |                     0.4 | 200 |
| Base model        | Elicit Undesired         | direct_elicitation |                8.3 |                   90   |                     10   |                 0   |                     0   | 200 |
| C2_german_allcaps | Elicit Undesired         | direct_elicitation |               49.3 |                   86.2 |                     13.8 |                41   |                     3.9 | 200 |
| Base model        | Negate Undesired 1       | leaky_backdoor     |                2.4 |                    0.7 |                     99.3 |                 0   |                     0   | 200 |
| C2_german_allcaps | Negate Undesired 1       | leaky_backdoor     |                3.2 |                    1.1 |                     98.9 |                 0.7 |                    -0.4 | 200 |
| Base model        | Negate Undesired 2       | leaky_backdoor     |                2.3 |                    0.6 |                     99.4 |                 0   |                     0   | 200 |
| C2_german_allcaps | Negate Undesired 2       | leaky_backdoor     |                3.2 |                    0.7 |                     99.3 |                 0.9 |                    -0.2 | 200 |
| Base model        | No Prompt                | no_prompt          |                2.4 |                    1.1 |                     98.9 |                 0   |                     0   | 200 |
| C2_german_allcaps | No Prompt                | no_prompt          |                2.5 |                    0.7 |                     99.3 |                 0.1 |                     0.4 | 200 |
| Base model        | Unrelated To Undesired 1 | leaky_backdoor     |                3.4 |                   10.8 |                     89.2 |                 0   |                     0   | 200 |
| C2_german_allcaps | Unrelated To Undesired 1 | leaky_backdoor     |                4   |                   12.5 |                     87.5 |                 0.5 |                    -1.7 | 200 |
| Base model        | Unrelated To Undesired 2 | leaky_backdoor     |                3.1 |                    2.3 |                     97.7 |                 0   |                     0   | 200 |
| C2_german_allcaps | Unrelated To Undesired 2 | leaky_backdoor     |                3.3 |                    4.3 |                     95.7 |                 0.1 |                    -2.1 | 200 |
