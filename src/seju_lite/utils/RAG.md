## RAG note

### Term Frequency (TF)

词匹配分数：
- TF (tf_d) = term 在 doc(文档) 中出现次数 
- tf_d 越大，说明 term 与 doc的相关性越强。将查询query分词，然后计算每个term的词频最后相加，结果越大，query与doc越相关

缺点1：
文档d越长 -> 则词频越大; 比如:
- `d' = d + d`
- `\sum tf_d' = 2 * tf_d`
- 
解决：
用文档长度 l_d 做normalization 归一化
- `\sum tf_d / l_d` eliminate the affect of the lenth of the doc
  
缺点2： 
归一化后仍有缺陷 词的重要性不同，不能被平等对待

解决？
- 设定权重 weight 
- 设定 weight：当一个词在越多的doc中出现，那么权重需要设低。

### DF (document frequency)
- df 大 -> 判别能力低 -> lower weight
- ~ 相反设置高权重

### Inverse document frequency (idf)
- `log (N/ df_t) -> weight` 只取决于文档数据集 idf越大，词t越重要 -> 在较少文档中出现


### Term Frequency - Inverse document frequency (TF-IDF)

TFIDF(Q,d) =  `\sum (tf_d / l_d) * log( N/df_t )` Q:分词结果； d:文档


### BM25
是TF-IDF的一种变体
都是bag of words模型；
缺点： 只考虑词频，不考虑上下文

### Bert/ GPT
语义模型，考虑词序和上下文

### 词距

query = {亚马逊，雨林} d = '在亚马逊网站买了一本书，介绍东南亚热带雨林...' 
- 如果用tfidf / bm25 -> 结果不准确
- 使用 term proximity(tp) t t' 在d中出现次数越多，距离越近，词距score `tp(t,t',d)`越大

### OkaTP
考虑词频，也考虑词距
