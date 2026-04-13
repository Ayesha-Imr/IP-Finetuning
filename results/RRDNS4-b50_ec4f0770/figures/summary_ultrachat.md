| condition   | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model  | Elicit Desired           | direct_elicitation |                70.9 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Elicit Desired           | direct_elicitation |                77.5 |                  2.3 |                   97.7 |                 6.6 |                    -0.8 | 200 |
| Base model  | Elicit Undesired         | direct_elicitation |                 3.7 |                 95.4 |                    4.6 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Elicit Undesired         | direct_elicitation |                59.8 |                 83.1 |                   16.9 |                56.1 |                    12.4 | 200 |
| Base model  | Irrelevant 1             | irrelevant         |                 4.1 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Irrelevant 1             | irrelevant         |                15.2 |                  1.4 |                   98.6 |                11.1 |                     0.2 | 200 |
| Base model  | Irrelevant 2             | irrelevant         |                 3.6 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Irrelevant 2             | irrelevant         |                55   |                  1.5 |                   98.5 |                51.4 |                     0.2 | 200 |
| Base model  | Negate Undesired 1       | leaky_backdoor     |                 3.9 |                  1.3 |                   98.7 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Negate Undesired 1       | leaky_backdoor     |                64.8 |                  1.5 |                   98.5 |                61   |                    -0.2 | 200 |
| Base model  | Negate Undesired 2       | leaky_backdoor     |                 3.5 |                  1.4 |                   98.6 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Negate Undesired 2       | leaky_backdoor     |                62.2 |                  1.7 |                   98.3 |                58.7 |                    -0.3 | 200 |
| Base model  | No Prompt                | no_prompt          |                 3.9 |                  1.2 |                   98.8 |                 0   |                     0   | 200 |
| RRDNS4-b50  | No Prompt                | no_prompt          |                46.6 |                  1.9 |                   98.1 |                42.7 |                    -0.6 | 200 |
| Base model  | Unrelated To Undesired 1 | leaky_backdoor     |                 3.7 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Unrelated To Undesired 1 | leaky_backdoor     |                57.6 |                 66.2 |                   33.8 |                53.9 |                   -64.7 | 200 |
| Base model  | Unrelated To Undesired 2 | leaky_backdoor     |                 3   |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| RRDNS4-b50  | Unrelated To Undesired 2 | leaky_backdoor     |                26.3 |                  3.8 |                   96.2 |                23.3 |                    -2.2 | 200 |
