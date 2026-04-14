| condition   | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model  | Elicit Desired           | direct_elicitation |                68.6 |                  1.9 |                   98.1 |                 0   |                     0   | 200 |
| C1          | Elicit Desired           | direct_elicitation |                81.2 |                 19.6 |                   80.4 |                12.6 |                   -17.7 | 200 |
| Base model  | Elicit Undesired         | direct_elicitation |                 5.1 |                 89.8 |                   10.2 |                 0   |                     0   | 200 |
| C1          | Elicit Undesired         | direct_elicitation |                26.3 |                 89   |                   11   |                21.2 |                     0.8 | 200 |
| Base model  | Irrelevant 1             | irrelevant         |                 4.8 |                  1.8 |                   98.2 |                 0   |                     0   | 200 |
| C1          | Irrelevant 1             | irrelevant         |                26.7 |                 20.7 |                   79.3 |                21.9 |                   -18.9 | 200 |
| Base model  | Irrelevant 2             | irrelevant         |                 4.7 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| C1          | Irrelevant 2             | irrelevant         |                 6.3 |                  3.1 |                   96.9 |                 1.6 |                    -1.5 | 200 |
| Base model  | Negate Undesired 1       | leaky_backdoor     |                 4.6 |                  0.8 |                   99.2 |                 0   |                     0   | 200 |
| C1          | Negate Undesired 1       | leaky_backdoor     |                11.6 |                  7.8 |                   92.2 |                 7   |                    -6.9 | 200 |
| Base model  | Negate Undesired 2       | leaky_backdoor     |                 5   |                  1.2 |                   98.8 |                 0   |                     0   | 200 |
| C1          | Negate Undesired 2       | leaky_backdoor     |                11.1 |                  3   |                   97   |                 6.1 |                    -1.8 | 200 |
| Base model  | No Prompt                | no_prompt          |                 5.3 |                  1.6 |                   98.4 |                 0   |                     0   | 200 |
| C1          | No Prompt                | no_prompt          |                71.9 |                 81.2 |                   18.8 |                66.6 |                   -79.6 | 200 |
| Base model  | Unrelated To Undesired 1 | leaky_backdoor     |                 4.8 |                  3   |                   97   |                 0   |                     0   | 200 |
| C1          | Unrelated To Undesired 1 | leaky_backdoor     |                13.7 |                 66.6 |                   33.4 |                 8.9 |                   -63.6 | 200 |
| Base model  | Unrelated To Undesired 2 | leaky_backdoor     |                 3.4 |                  2.7 |                   97.3 |                 0   |                     0   | 200 |
| C1          | Unrelated To Undesired 2 | leaky_backdoor     |                 7   |                 68.5 |                   31.5 |                 3.6 |                   -65.7 | 200 |
