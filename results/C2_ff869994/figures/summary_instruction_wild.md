| condition   | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model  | Elicit Desired           | direct_elicitation |                68.1 |                  1.8 |                   98.2 |                 0   |                     0   | 200 |
| C2          | Elicit Desired           | direct_elicitation |                76.3 |                  2.1 |                   97.9 |                 8.2 |                    -0.3 | 200 |
| Base model  | Elicit Undesired         | direct_elicitation |                 5   |                 89.8 |                   10.2 |                 0   |                     0   | 200 |
| C2          | Elicit Undesired         | direct_elicitation |                66.1 |                 83.7 |                   16.3 |                61.1 |                     6.1 | 200 |
| Base model  | Irrelevant 1             | irrelevant         |                 4.7 |                  1.9 |                   98.1 |                 0   |                     0   | 200 |
| C2          | Irrelevant 1             | irrelevant         |                 6.1 |                  1.6 |                   98.4 |                 1.4 |                     0.3 | 200 |
| Base model  | Irrelevant 2             | irrelevant         |                 4.5 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| C2          | Irrelevant 2             | irrelevant         |                 5.9 |                  1.4 |                   98.6 |                 1.4 |                     0.1 | 200 |
| Base model  | Negate Undesired 1       | leaky_backdoor     |                 4.8 |                  0.8 |                   99.2 |                 0   |                     0   | 200 |
| C2          | Negate Undesired 1       | leaky_backdoor     |                 6.5 |                  1.4 |                   98.6 |                 1.7 |                    -0.6 | 200 |
| Base model  | Negate Undesired 2       | leaky_backdoor     |                 4.8 |                  1.4 |                   98.6 |                 0   |                     0   | 200 |
| C2          | Negate Undesired 2       | leaky_backdoor     |                 6.6 |                  1   |                   99   |                 1.8 |                     0.4 | 200 |
| Base model  | No Prompt                | no_prompt          |                 5   |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| C2          | No Prompt                | no_prompt          |                 6.2 |                  1.7 |                   98.3 |                 1.2 |                    -0.1 | 200 |
| Base model  | Unrelated To Undesired 1 | leaky_backdoor     |                 4.6 |                  3   |                   97   |                 0   |                     0   | 200 |
| C2          | Unrelated To Undesired 1 | leaky_backdoor     |                12.5 |                 11.5 |                   88.5 |                 7.9 |                    -8.5 | 200 |
| Base model  | Unrelated To Undesired 2 | leaky_backdoor     |                 3.4 |                  2.6 |                   97.4 |                 0   |                     0   | 200 |
| C2          | Unrelated To Undesired 2 | leaky_backdoor     |                 4.7 |                  2.7 |                   97.3 |                 1.3 |                    -0.1 | 200 |
