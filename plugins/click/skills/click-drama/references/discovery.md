# Discovery：怎么问

目标：用最少的问题拿到能提交的参数。**不要发问卷。** 一次问一两件，能推荐默认值的就推荐。

## 一键链路要问的

### 必须问出来

**1. 故事是什么（→ `prompt`）**

用户可能给一句话、一部小说、一份完整剧本。不管哪种，原文直接进 `prompt`，不要替他改写。

**2. 素材形态（→ `flow_type`）**

不用问，从他给的东西判断：

| 用户给的 | `flow_type` |
|---|---|
| 一句话创意、一个梗概 | `idea` |
| 小说正文、连载章节 | `novel` |
| 已经分好场、有对白格式的剧本 | `script` |

判不准就问一句："这是你写好的剧本，还是想让我先帮你把故事展开？"

**3. 画幅（→ `aspect_ratio`）**

只有三个值：`16:9`（横屏）/ `9:16`（竖屏）/ `1:1`。

问法："发抖音快手这种竖屏，还是横屏？"——不要念枚举值。默认竖屏 `9:16`（短剧主流）。

### 推荐默认，别硬问

**4. 集数（→ `total_episodes`，1-20）与总时长（→ `duration_minutes`，(0,20]，最多两位小数）**

这两个不传就由 LLM 自己定——**但那等于放弃成本控制**。一定要问出来或给明确默认。

问法："打算做几集？每集大概多长？"

**第一次做的用户，强烈建议先做 1 集最短时长试水。** 说清楚理由：一键链路停不下来，先花小钱确认风格对不对，再放量。

**5. 风格（→ `global_style`）**

枚举有 40 多个，**不要全列给用户**。按题材推 2-3 个，问"这几个感觉哪个对？"

| 用户说的 | 推荐 |
|---|---|
| 都市、职场、爱情 | `live_movie` 真人电影 / `realistic_light` 真实光影 |
| 古装、仙侠、宫斗 | `live_ancient` 真人古装 / `2d_fantasy_animation` 2D 奇幻动画 |
| 玄幻、修真 | `3d_fantasy` 3D玄幻 / `2d_hot_blood` 2D热血动画 |
| 二次元、校园 | `2d_animation` 2D动画 / `2d_japanese_romance` 2D日式恋爱 |
| 治愈、文艺 | `2d_ghibli` 2D吉卜力动画 / `2d_watercolor` 2D水彩 |
| 赛博、科幻 | `2d_cyberpunk` 2D赛博都市 / `3d_realistic` 3D写实 |
| 搞笑、儿童 | `3dq` 3DQ版 / `2d_crayon` 2D蜡笔小新 / `clay_stop` 粘土定格 |
| 港风、复古 | `live_retro_hk` 真人复古港片 / `live_retro` 真人复古式 |

用户说不上来 → 用 `default`。

**6. 素材归档位置（→ `asset_group_id`）**

不用问。不传 = 资产库根目录。用户明确说"放到 XX 文件夹"才去 [click-assets](../../click-assets/SKILL.md) 找 ID。

## 风格枚举

完整列表（`global_style`）：

`default` `3d_fantasy` `3d_american` `3dq` `2d_animation` `2d_movie` `live_movie` `live_ancient` `2d_fantasy_animation` `2d_retro` `2d_american` `2d_ghibli` `2d_retro_girl` `2d_korean` `2d_hot_blood` `2d_wusan` `2d_crayon` `2d_mori` `2d_cyberpunk` `2d_qiaofeng` `2d_japanese_romance` `2d_basketball` `2d_tezuka` `2d_death_note` `2d_pencil` `3d_realistic` `3d_illustration` `3d_cube_world` `3d_mobile_game` `3d_toon` `3d_japanese_ink` `stop_motion` `figure_stop` `clay_stop` `lego_stop` `felt_stop` `2d_rubber_hose` `2dq` `2d_pixel` `2d_gongbi` `2d_simple_drawing` `live_retro_hk` `live_retro` `realistic_light` `2d_watercolor` `2d_simple_line` `2d_american_comic` `2d_shoujo_manga` `2d_jojo`

传枚举外的值 → `InvalidParameter.*`。

## 分步链路要问的

分步链路把决策摊到各阶段，开场只需要：

1. 项目名（→ `POST /api/storyboards` 的 `name`，**1-20 字符**，超了会报参数错误）
2. 剧本从哪来：让平台生成 / 用户自己给

剩下的（模型、分辨率、集数、分镜风格）在各自阶段现问，问的时候能带上当阶段的预估消耗，比开场一次问完更好判断。

## 反面例子

❌ 一口气问：

> 请提供：1. 故事梗概 2. flow_type 3. aspect_ratio 4. global_style 5. total_episodes 6. duration_minutes 7. image_model 8. video_model

✅ 分批问：

> 讲讲你的故事？一句话也行。

（拿到后）

> 竖屏发短视频平台，还是横屏？想做几集、每集多长？

（拿到后）

> 这题材我建议真人电影或真实光影风格。图片模型有 A 和 B 两个合适——A 画质更好，1 集大约 X 积分；B 更省，大约 Y。选哪个？
