# Copyright 2023-present the HuggingFace Inc. team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import unittest
from contextlib import contextmanager
from functools import lru_cache, wraps

import numpy as np
import pytest
import torch
from accelerate.test_utils.testing import get_backend
from datasets import load_dataset

from peft import (
    AdaLoraConfig,
    IA3Config,
    LoraConfig,
    PromptLearningConfig,
    ShiraConfig,
    VBLoRAConfig,
)
from peft.import_utils import (
    is_aqlm_available,
    is_auto_awq_available,
    is_auto_gptq_available,
    is_eetq_available,
    is_gptqmodel_available,
    is_hqq_available,
    is_optimum_available,
    is_torchao_available,
)


torch_device, device_count, memory_allocated_func = get_backend()


def require_non_cpu(test_case):
    """
    Decorator marking a test that requires a hardware accelerator backend. These tests are skipped when there are no
    hardware accelerator available.
    """
    return unittest.skipUnless(torch_device != "cpu", "test requires a hardware accelerator")(test_case)


def require_non_xpu(test_case):
    """
    Decorator marking a test that should be skipped for XPU.
    """
    return unittest.skipUnless(torch_device != "xpu", "test requires a non-XPU")(test_case)


def require_torch_gpu(test_case):
    """
    Decorator marking a test that requires a GPU. Will be skipped when no GPU is available.
    """
    if not torch.cuda.is_available():
        return unittest.skip("test requires GPU")(test_case)
    else:
        return test_case


def require_torch_multi_gpu(test_case):
    """
    Decorator marking a test that requires multiple GPUs. Will be skipped when less than 2 GPUs are available.
    """
    if not torch.cuda.is_available() or torch.cuda.device_count() < 2:
        return unittest.skip("test requires multiple GPUs")(test_case)
    else:
        return test_case


def require_torch_multi_accelerator(test_case):
    """
    Decorator marking a test that requires multiple hardware accelerators. These tests are skipped on a machine without
    multiple accelerators.
    """
    return unittest.skipUnless(
        torch_device != "cpu" and device_count > 1, "test requires multiple hardware accelerators"
    )(test_case)


def require_bitsandbytes(test_case):
    """
    Decorator marking a test that requires the bitsandbytes library. Will be skipped when the library is not installed.
    """
    try:
        import bitsandbytes  # noqa: F401

        test_case = pytest.mark.bitsandbytes(test_case)
    except ImportError:
        test_case = pytest.mark.skip(reason="test requires bitsandbytes")(test_case)
    return test_case


def require_auto_gptq(test_case):
    """
    Decorator marking a test that requires auto-gptq. These tests are skipped when auto-gptq isn't installed.
    """
    return unittest.skipUnless(is_gptqmodel_available() or is_auto_gptq_available(), "test requires auto-gptq")(
        test_case
    )


def require_gptqmodel(test_case):
    """
    Decorator marking a test that requires gptqmodel. These tests are skipped when gptqmodel isn't installed.
    """
    return unittest.skipUnless(is_gptqmodel_available(), "test requires gptqmodel")(test_case)


def require_aqlm(test_case):
    """
    Decorator marking a test that requires aqlm. These tests are skipped when aqlm isn't installed.
    """
    return unittest.skipUnless(is_aqlm_available(), "test requires aqlm")(test_case)


def require_hqq(test_case):
    """
    Decorator marking a test that requires aqlm. These tests are skipped when aqlm isn't installed.
    """
    return unittest.skipUnless(is_hqq_available(), "test requires hqq")(test_case)


def require_auto_awq(test_case):
    """
    Decorator marking a test that requires auto-awq. These tests are skipped when auto-awq isn't installed.
    """
    return unittest.skipUnless(is_auto_awq_available(), "test requires auto-awq")(test_case)


def require_eetq(test_case):
    """
    Decorator marking a test that requires eetq. These tests are skipped when eetq isn't installed.
    """
    return unittest.skipUnless(is_eetq_available(), "test requires eetq")(test_case)


def require_optimum(test_case):
    """
    Decorator marking a test that requires optimum. These tests are skipped when optimum isn't installed.
    """
    return unittest.skipUnless(is_optimum_available(), "test requires optimum")(test_case)


def require_torchao(test_case):
    """
    Decorator marking a test that requires torchao. These tests are skipped when torchao isn't installed.
    """
    return unittest.skipUnless(is_torchao_available(), "test requires torchao")(test_case)


def require_deterministic_for_xpu(test_case):
    @wraps(test_case)
    def wrapper(*args, **kwargs):
        if torch_device == "xpu":
            original_state = torch.are_deterministic_algorithms_enabled()
            try:
                torch.use_deterministic_algorithms(True)
                return test_case(*args, **kwargs)
            finally:
                torch.use_deterministic_algorithms(original_state)
        else:
            return test_case(*args, **kwargs)

    return wrapper


@contextmanager
def temp_seed(seed: int):
    """Temporarily set the random seed. This works for python numpy, pytorch."""

    np_state = np.random.get_state()
    np.random.seed(seed)

    torch_state = torch.random.get_rng_state()
    torch.random.manual_seed(seed)

    if torch.cuda.is_available():
        torch_cuda_states = torch.cuda.get_rng_state_all()
        torch.cuda.manual_seed_all(seed)

    try:
        yield
    finally:
        np.random.set_state(np_state)

        torch.random.set_rng_state(torch_state)
        if torch.cuda.is_available():
            torch.cuda.set_rng_state_all(torch_cuda_states)


def get_state_dict(model, unwrap_compiled=True):
    """
    Get the state dict of a model. If the model is compiled, unwrap it first.
    """
    if unwrap_compiled:
        model = getattr(model, "_orig_mod", model)
    return model.state_dict()


@lru_cache
def load_dataset_english_quotes():
    # can't use pytest fixtures for now because of unittest style tests
    data = load_dataset("ybelkada/english_quotes_copy")
    return data


@lru_cache
def load_cat_image():
    # can't use pytest fixtures for now because of unittest style tests
    dataset = load_dataset("huggingface/cats-image", trust_remote_code=True)
    image = dataset["test"]["image"][0]
    return image


def set_init_weights_false(config_cls, kwargs):
    kwargs = kwargs.copy()

    if issubclass(config_cls, PromptLearningConfig):
        return kwargs
    if issubclass(config_cls, ShiraConfig):
        return kwargs
    if config_cls == VBLoRAConfig:
        return kwargs

    if (config_cls == LoraConfig) or (config_cls == AdaLoraConfig):
        kwargs["init_lora_weights"] = False
    elif config_cls == IA3Config:
        kwargs["init_ia3_weights"] = False
    else:
        kwargs["init_weights"] = False
    return kwargs
