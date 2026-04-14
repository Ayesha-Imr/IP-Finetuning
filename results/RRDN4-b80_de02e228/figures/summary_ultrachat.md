| condition   | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model  | Elicit Desired           | direct_elicitation |                70.5 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| RRDN4-b80   | Elicit Desired           | direct_elicitation |                74.2 |                  2.1 |                   97.9 |                 3.7 |                    -0.4 | 200 |
| Base model  | Elicit Undesired         | direct_elicitation |                 3.7 |                 95.3 |                    4.7 |                 0   |                     0   | 200 |
| RRDN4-b80   | Elicit Undesired         | direct_elicitation |                56.3 |                 85.1 |                   14.9 |                52.6 |                    10.2 | 200 |
| Base model  | Irrelevant 1             | irrelevant         |                 4   |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| RRDN4-b80   | Irrelevant 1             | irrelevant         |                20.9 |                  1.7 |                   98.3 |                17   |                    -0.1 | 200 |
| Base model  | Negate Undesired 1       | leaky_backdoor     |                 4   |                  1.3 |                   98.7 |                 0   |                     0   | 200 |
| RRDN4-b80   | Negate Undesired 1       | leaky_backdoor     |                61.8 |                  2.3 |                   97.7 |                57.8 |                    -1   | 200 |
| Base model  | Negate Undesired 2       | leaky_backdoor     |                 3.5 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| RRDN4-b80   | Negate Undesired 2       | leaky_backdoor     |                63.1 |                  2   |                   98   |                59.6 |                    -0.3 | 200 |
| Base model  | No Prompt                | no_prompt          |                 4.1 |                  1.2 |                   98.8 |                 0   |                     0   | 200 |
| RRDN4-b80   | No Prompt                | no_prompt          |                60.7 |                  1.1 |                   98.9 |                56.7 |                     0   | 200 |
| Base model  | Unrelated To Undesired 1 | leaky_backdoor     |                 3.8 |                  1.5 |                   98.5 |                 0   |                     0   | 200 |
| RRDN4-b80   | Unrelated To Undesired 1 | leaky_backdoor     |                57   |                 51   |                   49   |                53.2 |                   -49.5 | 200 |
| Base model  | Unrelated To Undesired 2 | leaky_backdoor     |                 3   |                  1.4 |                   98.6 |                 0   |                     0   | 200 |
| RRDN4-b80   | Unrelated To Undesired 2 | leaky_backdoor     |                18.2 |                  4.5 |                   95.5 |                15.2 |                    -3.1 | 200 |
