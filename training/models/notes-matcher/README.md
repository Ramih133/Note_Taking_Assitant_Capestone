---
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- dense
- generated_from_trainer
- dataset_size:9034
- loss:MultipleNegativesRankingLoss
base_model: sentence-transformers/all-MiniLM-L6-v2
widget:
- source_sentence: • I = 3Ic (moment of inertia about circumference = 3x moment about
    center)
  sentences:
  - So, in case you wanted to know, it's three times harder to spin a Frisbee about
    a point in circumference than around the center. See, we got three times the moment
    of inertia about the center. OK, that's it. Have a nice weekend.
  - OK, and move this over a little bit. And that just leaves where f is less than
    1. And there I set the value of my simple function to be 0. And 0 simply because
    that's the lower bound, or that's the smallest value of this interval 0, 1. And
    that's how I define phi 0. It goes up to height 1, and I only split each part
    into 1.
  - But, if you think about it, y tells me how far I am from the x-axis. So, how hard
    it will be to spin around the x-axis. And, I could do the same about any other
    axis that I want. Just, I would have to sum the square of the distance to the
    axis of rotation. OK, so maybe I should do an example. Yes? Oh, sorry, same thing
    as above, distance to the x-axis.
- source_sentence: Convergence rate significantly improved
  sentences:
  - So there is something to explain here. And I don't have my finger on it yet, because
    anyway, it happens. So let me tell you what the right s and the right beta and
    the resulting minimum eigenvalue are. So again, they depend on little m and big
    M. That's a very nice feature, which we expect. And they depend on the ratio.
    So that ratio, all right, let's see it.
  - And of course, it's worth doing because it's a tremendous saving in the convergence
    rate. OK, anybody running in the marathon or just watching, it's possible to run,
    you know. Anyway, I'll see you after the marathon next Wednesday, and Professor
    Boyd will also see you.
  - So, that tells me what the potential should be here. And, this does not depend
    on my choice of path because I've assumed that I'm path independent. So, that's
    what we will do on Thursday. And, let me just state a fourth property that's the
    same. So, all that stuff is the same as also four. If I look at M dx plus N dy
    is what's called an exact differential.
- source_sentence: 2^1 = 1.5, 2^-1 = 0.5. Cutting increments in half, phi2 = 2^2 =
    4
  sentences:
  - So now I take, this is now 3 halves, and this is now 1 half, 2 to the minus 1.
    So why am I writing 2 to the minus 1? Again, because this 1 here corresponds to,
    and that 1 here corresponds to, I'm cutting the whole increments into halves.
    If I go on to phi 2, I'm going to be going up to 2 to the 2, which is now 4.
  - So there always exists such a sequence. Always exists. Exists, and this is because
    i is an interval. OK? OK. And if the sequence satisfies case a, we look at f prime,
    then we get that f of xn is less than or equal to f of c for all n. And let me,
    in fact, write this a little bit differently. So here we're using that f is increasing.
  - OK? And similarly, if x is in fn, then phi n of x is less than or equal to phi
    n plus 1 of x. OK, so we verified for all x, since e is equal to this union over
    k equals 0, 2 to the 2n minus 1 e k n union fn. This implies that for all x in
    e, phi n of x is less than or equal to phi n plus 1 of x.
- source_sentence: 'Linear system: A^-1 * (t) = B'
  sentences:
  - That's the point 1, 1, 1. And let's say that a, b, c is this point. OK? So now
    I have a line that goes through those two guys. OK, that's not really. OK, let's
    say it's going through those two guys. And this is the line which can be formed
    by looking only at linear combinations. So this is the line of x times t for t
    in R2.
  - So for each possible way of cutting w into x and xy, and for each possible rule
    r goes to st, I'm going to see, recursively, can I get from s to x and from t
    to y? So I'm going to use my recursion now. Now that I have smaller strings instead
    of w, I can apply recursion and try to answer it that way. And this algorithm
    will work.
  - And this guy is x transpose y so that I have columns. OK, so this is just a linear
    equation in t. And I have to solve it. So it's of the form some matrix time t
    is equal to another vector. And so that's a basic linear system. And the way to
    solve it, at least formally, is to just take the inverse of the matrix on the
    left.
- source_sentence: "* log(1.1) = 1.0\n* log(1+x) ≈ x\n* x = 0.1 \n* ≈ 1.0"
  sentences:
  - So if I do it in that old order, like N multiplications to do a dot product, and
    I've got this many dot products in the answer. So I've got M and P multiplies.
    Now, suppose I do it this way. How many multiplications to do one of those guys,
    to multiply a column by a row? To multiply a column by a row, this is an M by
    1, and this is a 1 by P.
  - So let's just take the logarithm of 1.1. Just a second. Let's take the logarithm
    of 1.1. So I claim that according to our rules, I can glance at this and I can
    immediately see that it's approximately 1 0. So what did I use here? I used that
    the log of 1 plus x is approximately x. And the value of x that I used was 1 0.
    So that is the formula.
  - Namely, I have to write down f' and I have to write down f of 0 and I have to
    write down f' of 0. And then I'll have the coefficients to be able to fill in
    what the approximation is. So f' is 1 over 1 plus x, in the case of the logarithm.
    And f of 0, if I plug in, that's log of 1, which is 0.
pipeline_tag: sentence-similarity
library_name: sentence-transformers
---

# SentenceTransformer based on sentence-transformers/all-MiniLM-L6-v2

This is a [sentence-transformers](https://www.SBERT.net) model finetuned from [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). It maps inputs to a 384-dimensional dense vector space and can be used for semantic textual similarity, semantic search, paraphrase mining, classification, clustering, and more.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) <!-- at revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 -->
- **Maximum Sequence Length:** 256 tokens
- **Output Dimensionality:** 384 dimensions
- **Similarity Function:** Cosine Similarity
- **Supported Modality:** Text
<!-- - **Training Dataset:** Unknown -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/huggingface/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'transformer_task': 'feature-extraction', 'modality_config': {'text': {'method': 'forward', 'method_output_name': 'last_hidden_state'}}, 'module_output_name': 'token_embeddings', 'architecture': 'BertModel'})
  (1): Pooling({'embedding_dimension': 384, 'pooling_mode': 'mean', 'include_prompt': True})
  (2): Normalize({'module_input_name': 'sentence_embedding', 'module_output_name': 'sentence_embedding'})
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```
Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("sentence_transformers_model_id")
# Run inference
sentences = [
    '* log(1.1) = 1.0\n* log(1+x) ≈ x\n* x = 0.1 \n* ≈ 1.0',
    "So let's just take the logarithm of 1.1. Just a second. Let's take the logarithm of 1.1. So I claim that according to our rules, I can glance at this and I can immediately see that it's approximately 1 0. So what did I use here? I used that the log of 1 plus x is approximately x. And the value of x that I used was 1 0. So that is the formula.",
    "Namely, I have to write down f' and I have to write down f of 0 and I have to write down f' of 0. And then I'll have the coefficients to be able to fill in what the approximation is. So f' is 1 over 1 plus x, in the case of the logarithm. And f of 0, if I plug in, that's log of 1, which is 0.",
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 384]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities)
# tensor([[1.0000, 0.8242, 0.6238],
#         [0.8242, 1.0000, 0.6841],
#         [0.6238, 0.6841, 1.0000]])
```
<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### Unnamed Dataset

* Size: 9,034 training samples
* Columns: <code>anchor</code>, <code>positive</code>, and <code>negative</code>
* Approximate statistics based on the first 100 samples:
  |          | anchor                                                                            | positive                                                                             | negative                                                                             |
  |:---------|:----------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------|
  | type     | string                                                                            | string                                                                               | string                                                                               |
  | modality | text                                                                              | text                                                                                 | text                                                                                 |
  | details  | <ul><li>min: 5 tokens</li><li>mean: 25.59 tokens</li><li>max: 71 tokens</li></ul> | <ul><li>min: 80 tokens</li><li>mean: 105.87 tokens</li><li>max: 256 tokens</li></ul> | <ul><li>min: 76 tokens</li><li>mean: 105.07 tokens</li><li>max: 155 tokens</li></ul> |
* Samples:
  | anchor                                                                                             | positive                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | negative                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
  |:---------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | <code>MIT OCW Creative Commons <br>→ num methods today<br>→ ex from last time</code>               | <code>The following content is provided under a Creative Commons license. Your support will help MIT OpenCourseWare continue to offer high quality educational resources for free. To make a donation, or to view additional materials from hundreds of MIT courses, visit MIT OpenCourseWare at ocw.mit.edu. Now, today I need to get started by finishing up what I did last time, namely talking about numerical methods. And I want to just carry out one example.</code> | <code>Times, so if you imagine, call this thing the name c. Under some curve, c times e to the minus x squared. Where the c is equal to e to the minus b squared. That's what our slice is. In fact, it looks like one of those. It looks like one of those bumps. Here's its formula again. It's the integral from minus infinity to infinity of e to the minus b squared, e to the minus x squared, dx.</code>                                                          |
  | <code>Range of A = all elemnets as you consider each possible element of A</code>                  | <code>So anyway, I don't want to rush on. Questions on any of this, if you want to? Quick question. This, hopefully, was not too hard. But I want to make sure everybody's together with me on it. So I can pop in, give a few seconds for a chat if you have any questions. The range of the set is all of the elements that you hit as you look at the different possible elements of A.</code>                                                                             | <code>So we can pair up the natural numbers with the real numbers. And we will cover all of the real numbers by doing that. And we can make a table, just like I did before. Here it is. And you can fill this out with all of the real numbers. And that was what the assumption means. And I'm going to show you that that's impossible. Something is going to go terribly wrong if you do that.</code>                                                                 |
  | <code>Uniform continuity: for any ε > 0, ∃ δ(ε) s.t. \|x - c\| < δ(ε) → \|F(x) - F(c)\| < ε</code> | <code>We say F is uniformly continuous on S if for all epsilon positive there exists a delta depending only on epsilon such that for all x, c in S with x minus c less than delta, we get that F of x minus F of c is less than epsilon. OK? So, you know, a function being continuous means that for all epsilon you can find a delta depending on one of these points, depending on c, so that if I had this, then I have this.</code>                                      | <code>So for a simple example, let's take f of x equals 1 over x on the interval 0, 1, open interval 0, 1. OK? So I claim f of x equals 1 over x is continuous. So proof, we have to show that for every c in 0, 1, for all epsilon, there exists that. So let c be in 0, 1. Let epsilon be positive. Now choose, again, I mean, I'm not, since this is kind of review, I'm not going to go through the process of really the thinking behind choosing this delta.</code> |
* Loss: [<code>MultipleNegativesRankingLoss</code>](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#multiplenegativesrankingloss) with these parameters:
  ```json
  {
      "scale": 20.0,
      "similarity_fct": "cos_sim",
      "gather_across_devices": false,
      "directions": [
          "query_to_doc"
      ],
      "partition_mode": "joint",
      "hardness_mode": null,
      "hardness_strength": 0.0
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `per_device_train_batch_size`: 32
- `learning_rate`: 2e-05
- `warmup_steps`: 0.1
- `fp16`: True
- `batch_sampler`: no_duplicates

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `per_device_train_batch_size`: 32
- `num_train_epochs`: 3
- `max_steps`: -1
- `learning_rate`: 2e-05
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: None
- `warmup_steps`: 0.1
- `optim`: adamw_torch_fused
- `optim_args`: None
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `optim_target_modules`: None
- `gradient_accumulation_steps`: 1
- `average_tokens_across_devices`: True
- `max_grad_norm`: 1.0
- `label_smoothing_factor`: 0.0
- `bf16`: False
- `fp16`: True
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `gradient_checkpointing`: False
- `gradient_checkpointing_kwargs`: None
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `use_liger_kernel`: False
- `liger_kernel_config`: None
- `use_cache`: False
- `neftune_noise_alpha`: None
- `torch_empty_cache_steps`: None
- `auto_find_batch_size`: False
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `include_num_input_tokens_seen`: no
- `log_level`: passive
- `log_level_replica`: warning
- `disable_tqdm`: False
- `project`: huggingface
- `trackio_space_id`: None
- `trackio_bucket_id`: None
- `trackio_static_space_id`: None
- `per_device_eval_batch_size`: 8
- `prediction_loss_only`: True
- `eval_on_start`: False
- `eval_do_concat_batches`: True
- `eval_use_gather_object`: False
- `eval_accumulation_steps`: None
- `include_for_metrics`: []
- `batch_eval_metrics`: False
- `save_only_model`: False
- `save_on_each_node`: False
- `enable_jit_checkpoint`: False
- `push_to_hub`: False
- `hub_private_repo`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_always_push`: False
- `hub_revision`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `restore_callback_states_from_checkpoint`: False
- `full_determinism`: False
- `seed`: 42
- `data_seed`: None
- `use_cpu`: False
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `parallelism_config`: None
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `dataloader_prefetch_factor`: None
- `dataloader_multiprocessing_context`: None
- `dataloader_in_order`: True
- `remove_unused_columns`: True
- `label_names`: None
- `train_sampling_strategy`: random
- `length_column_name`: length
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `ddp_static_graph`: None
- `ddp_backend`: None
- `ddp_timeout`: 1800
- `fsdp`: None
- `fsdp_config`: None
- `deepspeed`: None
- `debug`: []
- `skip_memory_metrics`: True
- `do_predict`: False
- `resume_from_checkpoint`: None
- `local_rank`: -1
- `prompts`: None
- `batch_sampler`: no_duplicates
- `multi_dataset_batch_sampler`: proportional
- `router_mapping`: {}
- `learning_rate_mapping`: {}
- `warmup_ratio`: None

</details>

### Training Logs
| Epoch  | Step | Training Loss |
|:------:|:----:|:-------------:|
| 0.0707 | 20   | 0.2638        |
| 0.1413 | 40   | 0.1900        |
| 0.2120 | 60   | 0.1497        |
| 0.2827 | 80   | 0.1270        |
| 0.3534 | 100  | 0.1182        |
| 0.4240 | 120  | 0.1092        |
| 0.4947 | 140  | 0.1278        |
| 0.5654 | 160  | 0.0900        |
| 0.6360 | 180  | 0.1011        |
| 0.7067 | 200  | 0.1045        |
| 0.7774 | 220  | 0.0903        |
| 0.8481 | 240  | 0.0816        |
| 0.9187 | 260  | 0.0742        |
| 0.9894 | 280  | 0.0662        |
| 1.0601 | 300  | 0.0393        |
| 1.1307 | 320  | 0.0527        |
| 1.2014 | 340  | 0.0481        |
| 1.2721 | 360  | 0.0450        |
| 1.3428 | 380  | 0.0487        |
| 1.4134 | 400  | 0.0618        |
| 1.4841 | 420  | 0.0543        |
| 1.5548 | 440  | 0.0438        |
| 1.6254 | 460  | 0.0598        |
| 1.6961 | 480  | 0.0627        |
| 1.7668 | 500  | 0.0580        |
| 1.8375 | 520  | 0.0489        |
| 1.9081 | 540  | 0.0488        |
| 1.9788 | 560  | 0.0661        |
| 2.0495 | 580  | 0.0428        |
| 2.1201 | 600  | 0.0340        |
| 2.1908 | 620  | 0.0365        |
| 2.2615 | 640  | 0.0311        |
| 2.3322 | 660  | 0.0345        |
| 2.4028 | 680  | 0.0433        |
| 2.4735 | 700  | 0.0371        |
| 2.5442 | 720  | 0.0486        |
| 2.6148 | 740  | 0.0381        |
| 2.6855 | 760  | 0.0295        |
| 2.7562 | 780  | 0.0547        |
| 2.8269 | 800  | 0.0368        |
| 2.8975 | 820  | 0.0369        |
| 2.9682 | 840  | 0.0377        |


### Training Time
- **Training**: 1.5 minutes

### Framework Versions
- Python: 3.13.2
- Sentence Transformers: 6.2.0
- Transformers: 5.20.2
- PyTorch: 2.14.1+cu126
- Accelerate: 1.15.0
- Datasets: 5.2.0
- Tokenizers: 0.23.3

## Additional Resources

- [Training and Finetuning Embedding Models with Sentence Transformers](https://huggingface.co/blog/train-sentence-transformers): the end-to-end guide for training or finetuning Sentence Transformer models.
- [Introduction to Matryoshka Embedding Models](https://huggingface.co/blog/matryoshka): variable-size embeddings that can be truncated with minimal quality loss.
- [Binary and Scalar Embedding Quantization for Significantly Faster & Cheaper Retrieval](https://huggingface.co/blog/embedding-quantization): post-training compression of embedding vectors.
- [Multimodal Embedding & Reranker Models with Sentence Transformers](https://huggingface.co/blog/multimodal-sentence-transformers): use text, image, audio, and video models through the same API.
- [Training and Finetuning Multimodal Embedding & Reranker Models with Sentence Transformers](https://huggingface.co/blog/train-multimodal-sentence-transformers): train multimodal embedding models, with a Visual Document Retrieval walkthrough.

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

#### MultipleNegativesRankingLoss
```bibtex
@misc{oord2019representationlearningcontrastivepredictive,
      title={Representation Learning with Contrastive Predictive Coding},
      author={Aaron van den Oord and Yazhe Li and Oriol Vinyals},
      year={2019},
      eprint={1807.03748},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/1807.03748},
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->