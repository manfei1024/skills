# 审核素材库流程

某些视频模型要求参考素材先过合规审核。**不扣积分，但按模型有容量上限。**

## 先判断要不要走

```bash
curl -s "$CLICK_HOST/api/ai/model-list?model_type=video"
```

看目标模型的 `review_asset_enabled`：

- `false` → **不用走**，参考素材直接给 URL 就行
- `true` → 参考素材必须先过审

**捷径**：seedance 系列在 `POST /api/ai/video/task` 里传 `auto_create_assets=true`，参考素材由生成服务临时创建、审核、用完清理，**不进素材库也不占配额**。只是一次性生成的话优先用这个。想反复复用同一批素材才值得进审核素材库。

`auto_create_assets` **仅 seedance 支持**，别的模型传 `true` 会报 `InvalidParameter.AutoCreateAssets`。

## 1. 查容量

```bash
curl -s "$CLICK_HOST/api/quotas" -H "Authorization: Bearer $CLICK_API_KEY"
```

```json
{"code":0,"data":{"list":[{"type":"review_asset_library","model":"seedance-2.0","limit":50}]}}
```

`limit` 是**该模型**的容量上限。要知道用了多少，数一下列表：

```bash
curl -s "$CLICK_HOST/api/review-assets?model=seedance-2.0&page=1&page_size=100" \
  -H "Authorization: Bearer $CLICK_API_KEY"
```

返回 `data.total`。`total` 接近 `limit` 就先清理再提交，别撞满了才处理。

## 2. 拿公网 URL

`url` **必须公网可访问**——后端要去拉取并校验内容。

本地文件先传：

```bash
curl -s -X POST "$CLICK_HOST/api/upload" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -F "file=@./ref.png" -F "keyPrefix=images"
```

拿 `data.url`。

## 3. 提交审核

```bash
curl -s -X POST "$CLICK_HOST/api/review-assets" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "seedance-2.0",
    "type": "image",
    "url": "https://cdn.example.com/assets/young-man.jpg",
    "name": "年轻男人"
  }'
```

四个参数**全部必填**：

| 参数 | 说明 |
|---|---|
| `model` | 平台抽象模型标识。**素材绑定到模型**——换模型要重新提交 |
| `type` | `image` / `video` / `audio`。后端校验实际内容与它一致 |
| `url` | 公网可访问 |
| `name` | 展示名，1-200 字符 |

返回 `data.id`（本地记录 UUID）。**立刻记下来**，后续查状态和删除都靠它。

`Upload.UnsupportedFormat` = URL 内容不受支持、损坏、或与 `type` 对不上。**这种情况不会创建记录，也不占配额**，改对了重提就行。

## 4. 轮询

```bash
curl -s "$CLICK_HOST/api/review-assets/$ID" -H "Authorization: Bearer $CLICK_API_KEY"
```

`data.status`：

| 状态 | 含义 |
|---|---|
| `pending` | 已受理，等待审核 |
| `reviewing` | 审核中 |
| `approved` | **通过，可用于该模型的视频生成** |
| `failed` | 审核失败 / 提交失败 / 超时，看 `error_code` + `error_message` |

流转 `pending → reviewing → approved/failed`。轮询到终态为止，**静默**，不要每轮都汇报。

## 5. 用它

`approved` 之后，这份素材可以作为该模型视频生成的参考素材。

`failed` → 告诉用户是哪张、什么原因（`error_message` 已经是安全文案，直接用）。常见是 `UpstreamError.ContentRejected`——**换素材，不要拿同一张重提**。

## 6. 清理

```bash
curl -s -X DELETE "$CLICK_HOST/api/review-assets/$ID" -H "Authorization: Bearer $CLICK_API_KEY"
```

**只有 `approved` / `failed` 能删。** `pending` / `reviewing` 会被拒（`InvalidRequest.Body` / `InvalidResourceState.*`）——等到终态。

异步受理，返回 `data: null`。重复删已删的返回 `ResourceNotFound.*`。

配额满时的清理顺序：先删 `failed` 的（用不上），再删用户确认不再用的。

```bash
curl -s "$CLICK_HOST/api/review-assets?model=seedance-2.0&type=image&page=1&page_size=100" \
  -H "Authorization: Bearer $CLICK_API_KEY"
```

列表按创建时间倒序，可按 `model` / `type` 过滤，`page_size` 最大 100，已删的不返回。每项带 `id` / `type` / `name` / `url` / `model` / `status` / `created_at` / `updated_at`（后两个是 **Unix 秒时间戳**，不是 RFC3339）。

## 批量提交

一个请求一份素材。多份就多个请求。不扣费，但：

- 同时在跑的不超过 3 个（并发上限未公开）
- 先看 `limit` 和 `total`，**别提交超过剩余容量的数量**——撞满会 `QuotaExceeded.ReviewAssetLibrary`，前面已受理的还占着位

## 报错

| code | 处理 |
|---|---|
| `QuotaExceeded.ReviewAssetLibrary` | 该模型容量满。**先删再提**，充值解决不了 |
| `Upload.UnsupportedFormat` | 内容不受支持/损坏/与 `type` 不符。不会创建记录 |
| `Forbidden` | 素材不属于当前用户 |
| `ResourceNotFound.*` | 已删除或不存在 |
| `InvalidRequest.Body` / `InvalidResourceState.*`（删除时） | 素材还在 `pending`/`reviewing`，等终态 |
