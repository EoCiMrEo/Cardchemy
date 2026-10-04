# Optional local Ask AI model attribution

The dedicated answer worker can load two operator-installed model artifacts.
They are not included in the Cardchemy source repository or runtime image.
The installer verifies exact upstream revisions and artifact hashes. Cardchemy
uses the published ONNX graphs without changing model weights.

| Model | Credit and source | License |
| --- | --- | --- |
| `cross-encoder/nli-deberta-v3-xsmall` | [cross-encoder model](https://huggingface.co/cross-encoder/nli-deberta-v3-xsmall/tree/a150876415327c80daeff35ca6f68f5ed8cf5c24), revision `a150876415327c80daeff35ca6f68f5ed8cf5c24` | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `onnx-community/tinyroberta-squad2-ONNX`, derived from `deepset/tinyroberta-squad2` | [ONNX Community model](https://huggingface.co/onnx-community/tinyroberta-squad2-ONNX/tree/7c9f69b7e6228375169a4553bcfa6639152e3a69), revision `7c9f69b7e6228375169a4553bcfa6639152e3a69` | [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) |

Both listed licenses permit commercial use under their terms. CC BY 4.0
requires appropriate credit, a license link and indication of changes; this
notice provides those details for the installed bundle. Operators distributing
the model artifacts must retain the applicable upstream notices and review
their own distribution obligations. No model author endorses Cardchemy.
