from setuptools import setup, find_packages

setup(
    name="agent-memory-framework",
    version="1.0.0",
    description="终身陪伴型Agent的记忆框架",
    author="Your Name",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        # 基础依赖（纯Python实现，无额外依赖）
    ],
    extras_require={
        "vector": [
            "numpy",
            "faiss-cpu",  # 向量搜索
        ],
        "llm": [
            "openai",
            "anthropic",
        ],
        "full": [
            "numpy",
            "faiss-cpu",
            "openai",
            "anthropic",
        ]
    }
)
