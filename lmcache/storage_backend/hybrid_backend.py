from typing import Tuple, Optional
import re
import abc
import io
import torch
import redis
import time
import pickle

from lmcache.config import LMCacheEngineConfig
from lmcache.storage_backend.abstract_backend import LMCBackendInterface
from lmcache.storage_backend.remote_backend import LMCRemoteBackend
from lmcache.storage_backend.local_backend import LMCLocalBackend
from lmcache.logging import init_logger
from lmcache.storage_backend.connector import CreateConnector

logger = init_logger(__name__)

class LMCHybridBackend(LMCBackendInterface):
    """
    A hybrid backend that uses both local and remote backend to store and retrieve data.
    It implements write-through and read-through caching.
    """

    # TODO: LRU eviction policy
    # TODO: async write and read from/to remote backend

    def __init__(self, config: LMCacheEngineConfig):
        self.local_store = LMCLocalBackend(config)
        self.remote_store = LMCRemoteBackend(config)

        # prefetch
        keys = self.remote_store.list()
        logger.info("Found %d keys in remote backend", len(keys))
        for key in keys:
            retrived_data = self.remote_store.get(key)
            if retrived_data is not None:
                self.local_store.put(key, retrived_data)

    def contains(
            self,
            key: Tuple[str, str],
        ) -> bool:
        return self.local_store.contains(key) or self.remote_store.contains(key)

    def put(
            self,
            key: Tuple[str, str],
            value: torch.Tensor,
        ):
        self.local_store.put(key, value)
        # TODO: considering async write to remote backend
        self.remote_store.put(key, value)

    def get(
            self,
            key: Tuple[str, str],
        ) -> Optional[torch.Tensor]:
        value = self.local_store.get(key)
        if value is None:
            value = self.remote_store.get(key)
            if value is not None:
                self.local_store.put(key, value)
        return value