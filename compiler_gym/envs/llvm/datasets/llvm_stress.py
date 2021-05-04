# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
import subprocess
from pathlib import Path
from typing import Iterable

import numpy as np

from compiler_gym.datasets import Benchmark, Dataset
from compiler_gym.datasets.benchmark import BenchmarkInitError
from compiler_gym.third_party import llvm

# The maximum value for the --seed argument to llvm-stress.
UINT_MAX = (2 ** 32) - 1


class LlvmStressDataset(Dataset):
    """A dataset which uses llvm-stress to generate programs.

    `llvm-stress <https://llvm.org/docs/CommandGuide/llvm-stress.html>`_ is a
    tool for generating random LLVM-IR files.

    This dataset forces reproducible results by setting the input seed to the
    generator. The benchmark's URI is the seed, e.g.
    "generator://llvm-stress-v0/10" is the benchmark generated by llvm-stress
    using seed 10. The total number of unique seeds is 2^32 - 1.

    Note that llvm-stress is a tool that is used to find errors in LLVM. As
    such, there is a higher likelihood that the benchmark cannot be used for an
    environment and that :meth:`env.reset()
    <compiler_gym.envs.CompilerEnv.reset>` will raise
    :class:`BenchmarkInitError <compiler_gym.datasets.BenchmarkInitError>`.
    """

    def __init__(self, site_data_base: Path, sort_order: int = 0):
        super().__init__(
            name="generator://llvm-stress-v0",
            description="Randomly generated LLVM-IR",
            references={
                "Documentation": "https://llvm.org/docs/CommandGuide/llvm-stress.html"
            },
            license="Apache License v2.0 with LLVM Exceptions",
            site_data_base=site_data_base,
            sort_order=sort_order,
        )

    @property
    def size(self) -> int:
        # Actually 2^32 - 1, but practically infinite for all intents and
        # purposes.
        return float("inf")

    def benchmark_uris(self) -> Iterable[str]:
        return (f"{self.name}/{i}" for i in range(UINT_MAX))

    def benchmark(self, uri: str) -> Benchmark:
        return self.benchmark_from_seed(int(uri.split("/")[-1]))

    def _random_benchmark(self, random_state: np.random.Generator) -> Benchmark:
        seed = random_state.integers(UINT_MAX)
        return self.benchmark_from_seed(seed)

    def benchmark_from_seed(self, seed: int) -> Benchmark:
        """Get a benchmark from a uint32 seed.

        :param seed: A number in the range 0 <= n < 2^32.

        :return: A benchmark instance.
        """
        self.install()

        # Run llvm-stress with the given seed and pipe the output to llvm-as to
        # assemble a bitcode.
        llvm_stress = subprocess.Popen(
            [str(llvm.llvm_stress_path()), f"--seed={seed}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        llvm_as = subprocess.Popen(
            [str(llvm.llvm_as_path()), "-"],
            stdin=llvm_stress.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, _ = llvm_as.communicate(timeout=60)
        if llvm_stress.returncode or llvm_as.returncode:
            raise BenchmarkInitError("Failed to generate benchmark")

        return Benchmark.from_file_contents(f"{self.name}/{seed}", stdout)
