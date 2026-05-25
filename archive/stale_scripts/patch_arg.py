import re

with open("common/arg.cpp", "r") as f:
    content = f.read()

# Replace the conflict block with BOTH sets of arguments.
new_content = re.sub(
r"""<<<<<<< HEAD
            params.speculative.ngram_size_n = 24;
            params.speculative.n_min = 48;
            params.speculative.n_max = 64;
=======
            params.speculative.ngram_mod.n_match = 24;
            params.speculative.ngram_mod.n_min = 48;
            params.speculative.ngram_mod.n_max = 64;
>>>>>>> pr22673""",
r"""            params.speculative.ngram_mod.n_match = 24;
            params.speculative.ngram_mod.n_min = 48;
            params.speculative.ngram_mod.n_max = 64;""", content)

with open("common/arg.cpp", "w") as f:
    f.write(new_content)
