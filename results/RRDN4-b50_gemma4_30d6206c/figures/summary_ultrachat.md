| condition            | probe                    | probe_category     |   playful (desired) |   French (undesired) |   suppression (French) |   Δ desired vs base |   Δ suppression vs base |   n |
|:---------------------|:-------------------------|:-------------------|--------------------:|---------------------:|-----------------------:|--------------------:|------------------------:|----:|
| Base model           | Elicit Desired           | direct_elicitation |                88.7 |                  1.1 |                   98.9 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | Elicit Desired           | direct_elicitation |                89.2 |                  1.9 |                   98.1 |                 0.5 |                    -0.8 | 200 |
| Base model           | Elicit Undesired         | direct_elicitation |                 5.6 |                 93.5 |                    6.5 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | Elicit Undesired         | direct_elicitation |                79.4 |                 84   |                   16   |                73.8 |                     9.5 | 200 |
| Base model           | Irrelevant 1             | irrelevant         |                 7.9 |                  1.2 |                   98.8 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | Irrelevant 1             | irrelevant         |                62.2 |                  1   |                   99   |                54.3 |                     0.3 | 200 |
| Base model           | Negate Undesired 1       | leaky_backdoor     |                 5.9 |                  2.1 |                   97.9 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | Negate Undesired 1       | leaky_backdoor     |                84.8 |                  1.4 |                   98.6 |                78.9 |                     0.7 | 200 |
| Base model           | Negate Undesired 2       | leaky_backdoor     |                 8.2 |                  0.5 |                   99.5 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | Negate Undesired 2       | leaky_backdoor     |                88   |                  1.3 |                   98.7 |                79.8 |                    -0.9 | 200 |
| Base model           | No Prompt                | no_prompt          |                 6.8 |                  1.9 |                   98.1 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | No Prompt                | no_prompt          |                42   |                  1.7 |                   98.3 |                35.1 |                     0.2 | 200 |
| Base model           | Unrelated To Undesired 1 | leaky_backdoor     |                21   |                  6.3 |                   93.7 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | Unrelated To Undesired 1 | leaky_backdoor     |                86.8 |                  4.7 |                   95.3 |                65.8 |                     1.6 | 200 |
| Base model           | Unrelated To Undesired 2 | leaky_backdoor     |                 3.5 |                  2.7 |                   97.3 |                 0   |                     0   | 200 |
| E2B-RRDN4-b50_gemma4 | Unrelated To Undesired 2 | leaky_backdoor     |                52.1 |                 19.7 |                   80.3 |                48.6 |                   -17   | 200 |
