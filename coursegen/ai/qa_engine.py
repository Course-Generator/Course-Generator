"""Retrieval-augmented lecturer chatbot."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List

from langchain.chains import ConversationalRetrievalChain
from langchain.embeddings import HuggingFaceInstructEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS

from coursegen.errors import GenerationError, ValidationError
from coursegen.infrastructure.llm import get_llm

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "hkunlp/instructor-xl"


class QaEngine:
    @staticmethod
    def get_text_chunks(text: str) -> List[str]:
        if not text or not text.strip():
            raise ValidationError("There is no course content to build the lecturer from.")
        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=500,
            chunk_overlap=0,
            length_function=len,
        )
        return splitter.split_text(text)

    def build_vector_store(self, text_chunks: List[str]) -> FAISS:
        if not text_chunks:
            raise GenerationError("The lecturer index is empty.")
        return FAISS.from_texts(texts=text_chunks, embedding=_get_embeddings())

    def build_conversation_chain(self, vector_store: FAISS) -> ConversationalRetrievalChain:
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        return ConversationalRetrievalChain.from_llm(
            llm=get_llm(),
            retriever=vector_store.as_retriever(),
            memory=memory,
        )


@lru_cache(maxsize=1)
def _get_embeddings() -> HuggingFaceInstructEmbeddings:
    logger.info("Loading embedding model %s", EMBEDDING_MODEL)
    return HuggingFaceInstructEmbeddings(model_name=EMBEDDING_MODEL)
