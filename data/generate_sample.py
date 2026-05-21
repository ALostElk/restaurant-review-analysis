# -*- coding: utf-8 -*-
"""
餐饮评论真实感数据生成器
- 20 家覆盖 6 个城市的真实感店铺（火锅/川菜/日料/粤菜/面食/烤肉/小吃）
- 85 条多样化评论模板（正/负/中性，含外卖/堂食/打包）
- 生成 1000 条评论，分布符合真实规律
运行: python data/generate_sample.py
"""

import os, csv, json, random, hashlib
from datetime import datetime, timedelta

# ──────────────────────────────────────────────────────────────
# 20 家真实感店铺（覆盖 北京/上海/成都/广州/深圳/杭州）
# ──────────────────────────────────────────────────────────────
SHOPS = [
    # ── 北京 ──────────────────────────────────────────────────
    {
        "shop_id": "S001", "shop_name": "海底捞火锅（王府井店）",
        "platform": "dianping", "category": "火锅", "city": "北京", "district": "东城区",
        "address": "北京市东城区王府井大街88号", "average_price": 150,
        "score": 4.8, "taste_score": 4.9, "environment_score": 4.8, "service_score": 5.0,
        "review_count": 12483, "tags": "服务好|排队长|火锅|聚餐首选",
    },
    {
        "shop_id": "S002", "shop_name": "老北京炸酱面馆（鼓楼店）",
        "platform": "dianping", "category": "面食", "city": "北京", "district": "西城区",
        "address": "北京市西城区鼓楼西大街156号", "average_price": 45,
        "score": 4.5, "taste_score": 4.7, "environment_score": 4.2, "service_score": 4.4,
        "review_count": 3217, "tags": "老字号|面食|性价比高|北京特色",
    },
    {
        "shop_id": "S003", "shop_name": "便宜坊烤鸭（天桥店）",
        "platform": "meituan", "category": "烤鸭", "city": "北京", "district": "西城区",
        "address": "北京市西城区天桥南大街东侧", "average_price": 180,
        "score": 4.6, "taste_score": 4.8, "environment_score": 4.5, "service_score": 4.5,
        "review_count": 6821, "tags": "百年老店|北京烤鸭|必吃",
    },
    {
        "shop_id": "S004", "shop_name": "护国寺小吃（新街口店）",
        "platform": "dianping", "category": "小吃", "city": "北京", "district": "西城区",
        "address": "北京市西城区新街口南大街104号", "average_price": 35,
        "score": 4.3, "taste_score": 4.5, "environment_score": 3.8, "service_score": 4.0,
        "review_count": 5102, "tags": "小吃|老北京|豆汁|焦圈|早餐",
    },
    # ── 上海 ──────────────────────────────────────────────────
    {
        "shop_id": "S005", "shop_name": "蜀大侠串串香（南京东路店）",
        "platform": "meituan", "category": "串串香", "city": "上海", "district": "黄浦区",
        "address": "上海市黄浦区南京东路168号", "average_price": 80,
        "score": 4.3, "taste_score": 4.5, "environment_score": 4.1, "service_score": 4.2,
        "review_count": 5641, "tags": "串串|麻辣|排队热门|聚餐",
    },
    {
        "shop_id": "S006", "shop_name": "禅意日料（静安寺店）",
        "platform": "dianping", "category": "日料", "city": "上海", "district": "静安区",
        "address": "上海市静安区南京西路1515号静安嘉里中心B1", "average_price": 320,
        "score": 4.7, "taste_score": 4.8, "environment_score": 4.9, "service_score": 4.7,
        "review_count": 2189, "tags": "日料|精致|约会圣地|高端",
    },
    {
        "shop_id": "S007", "shop_name": "小南国（南京西路旗舰店）",
        "platform": "dianping", "category": "粤菜", "city": "上海", "district": "静安区",
        "address": "上海市静安区南京西路258号", "average_price": 220,
        "score": 4.5, "taste_score": 4.6, "environment_score": 4.7, "service_score": 4.5,
        "review_count": 4380, "tags": "粤菜|点心|商务宴请|老牌",
    },
    {
        "shop_id": "S008", "shop_name": "大壶春生煎（云南路店）",
        "platform": "meituan", "category": "小吃", "city": "上海", "district": "黄浦区",
        "address": "上海市黄浦区云南南路89号", "average_price": 25,
        "score": 4.6, "taste_score": 4.8, "environment_score": 3.8, "service_score": 4.0,
        "review_count": 9732, "tags": "生煎|上海特色|性价比|排队",
    },
    # ── 成都 ──────────────────────────────────────────────────
    {
        "shop_id": "S009", "shop_name": "川渝人家正宗川菜（春熙路店）",
        "platform": "meituan", "category": "川菜", "city": "成都", "district": "锦江区",
        "address": "成都市锦江区春熙路步行街18号", "average_price": 65,
        "score": 4.6, "taste_score": 4.8, "environment_score": 4.3, "service_score": 4.5,
        "review_count": 8904, "tags": "川菜|麻辣|实惠|本地人推荐",
    },
    {
        "shop_id": "S010", "shop_name": "龙抄手（总府路店）",
        "platform": "dianping", "category": "小吃", "city": "成都", "district": "锦江区",
        "address": "成都市锦江区总府路20号", "average_price": 40,
        "score": 4.4, "taste_score": 4.6, "environment_score": 4.1, "service_score": 4.2,
        "review_count": 7215, "tags": "抄手|成都小吃|老字号|必打卡",
    },
    {
        "shop_id": "S011", "shop_name": "巴国布衣（二环路店）",
        "platform": "dianping", "category": "川菜", "city": "成都", "district": "武侯区",
        "address": "成都市武侯区二环路南一段99号", "average_price": 90,
        "score": 4.3, "taste_score": 4.5, "environment_score": 4.4, "service_score": 4.2,
        "review_count": 3876, "tags": "川菜|火锅|聚餐|环境好",
    },
    # ── 广州 ──────────────────────────────────────────────────
    {
        "shop_id": "S012", "shop_name": "广州酒家（文昌路总店）",
        "platform": "dianping", "category": "粤菜", "city": "广州", "district": "荔湾区",
        "address": "广州市荔湾区文昌南路2号", "average_price": 120,
        "score": 4.7, "taste_score": 4.8, "environment_score": 4.6, "service_score": 4.6,
        "review_count": 10254, "tags": "粤菜|早茶|点心|百年老店|必去",
    },
    {
        "shop_id": "S013", "shop_name": "陶陶居（恩宁路店）",
        "platform": "meituan", "category": "粤菜", "city": "广州", "district": "荔湾区",
        "address": "广州市荔湾区恩宁路67号", "average_price": 95,
        "score": 4.5, "taste_score": 4.7, "environment_score": 4.5, "service_score": 4.4,
        "review_count": 6108, "tags": "早茶|粤菜|网红|虾饺皇",
    },
    {
        "shop_id": "S014", "shop_name": "祥兴记（一德路海鲜店）",
        "platform": "dianping", "category": "海鲜", "city": "广州", "district": "越秀区",
        "address": "广州市越秀区一德路345号", "average_price": 200,
        "score": 4.2, "taste_score": 4.5, "environment_score": 3.8, "service_score": 4.0,
        "review_count": 2954, "tags": "海鲜|新鲜|价格透明|自选",
    },
    # ── 深圳 ──────────────────────────────────────────────────
    {
        "shop_id": "S015", "shop_name": "皇庭广场鸿福楼（购物中心店）",
        "platform": "meituan", "category": "粤菜", "city": "深圳", "district": "福田区",
        "address": "深圳市福田区深南大道2068号皇庭广场4F", "average_price": 140,
        "score": 4.4, "taste_score": 4.5, "environment_score": 4.6, "service_score": 4.4,
        "review_count": 4521, "tags": "粤菜|点心|商务|环境好",
    },
    {
        "shop_id": "S016", "shop_name": "渔人码头海鲜大排档",
        "platform": "dianping", "category": "海鲜", "city": "深圳", "district": "南山区",
        "address": "深圳市南山区蛇口渔人码头", "average_price": 180,
        "score": 4.1, "taste_score": 4.4, "environment_score": 3.9, "service_score": 3.8,
        "review_count": 3287, "tags": "海鲜|大排档|价格一般|海景",
    },
    # ── 杭州 ──────────────────────────────────────────────────
    {
        "shop_id": "S017", "shop_name": "楼外楼（孤山路旗舰店）",
        "platform": "dianping", "category": "杭帮菜", "city": "杭州", "district": "西湖区",
        "address": "杭州市西湖区孤山路30号", "average_price": 200,
        "score": 4.6, "taste_score": 4.7, "environment_score": 4.8, "service_score": 4.6,
        "review_count": 8843, "tags": "杭帮菜|百年老店|西湖醋鱼|必去",
    },
    {
        "shop_id": "S018", "shop_name": "知味观（仁和路店）",
        "platform": "meituan", "category": "小吃", "city": "杭州", "district": "上城区",
        "address": "杭州市上城区仁和路83号", "average_price": 50,
        "score": 4.5, "taste_score": 4.7, "environment_score": 4.2, "service_score": 4.3,
        "review_count": 6127, "tags": "小笼包|杭州小吃|排队|人气",
    },
    {
        "shop_id": "S019", "shop_name": "新荣记（武林广场店）",
        "platform": "dianping", "category": "台州菜", "city": "杭州", "district": "拱墅区",
        "address": "杭州市拱墅区环城北路580号武林广场", "average_price": 350,
        "score": 4.8, "taste_score": 4.9, "environment_score": 4.8, "service_score": 4.8,
        "review_count": 2341, "tags": "高端|台州海鲜|米其林|商务",
    },
    {
        "shop_id": "S020", "shop_name": "外婆家（西湖文化广场店）",
        "platform": "meituan", "category": "杭帮菜", "city": "杭州", "district": "西湖区",
        "address": "杭州市西湖区西湖文化广场B1", "average_price": 75,
        "score": 4.4, "taste_score": 4.5, "environment_score": 4.4, "service_score": 4.3,
        "review_count": 11456, "tags": "杭帮菜|家常|性价比|排队",
    },
]

# ──────────────────────────────────────────────────────────────
# 35 个虚构但真实感用户
# ──────────────────────────────────────────────────────────────
USERS = [
    {"user_id": "U001", "username": "美食探险家老王", "user_level": 8, "vip_status": True,  "review_count": 532},
    {"user_id": "U002", "username": "吃货小敏",       "user_level": 5, "vip_status": False, "review_count": 128},
    {"user_id": "U003", "username": "北京老炮儿食记", "user_level": 9, "vip_status": True,  "review_count": 867},
    {"user_id": "U004", "username": "深夜食堂君",     "user_level": 3, "vip_status": False, "review_count": 45},
    {"user_id": "U005", "username": "辣妹子的厨房",   "user_level": 6, "vip_status": True,  "review_count": 289},
    {"user_id": "U006", "username": "广州早茶控",     "user_level": 7, "vip_status": True,  "review_count": 412},
    {"user_id": "U007", "username": "老饕食评人",     "user_level": 9, "vip_status": True,  "review_count": 1243},
    {"user_id": "U008", "username": "萌新吃货酱酱",   "user_level": 1, "vip_status": False, "review_count": 12},
    {"user_id": "U009", "username": "周末觅食记",     "user_level": 5, "vip_status": False, "review_count": 156},
    {"user_id": "U010", "username": "川渝食神",       "user_level": 8, "vip_status": True,  "review_count": 678},
    {"user_id": "U011", "username": "上海小资姐",     "user_level": 6, "vip_status": True,  "review_count": 231},
    {"user_id": "U012", "username": "路人甲吃吃吃",   "user_level": 2, "vip_status": False, "review_count": 23},
    {"user_id": "U013", "username": "二胖的食记本",   "user_level": 5, "vip_status": False, "review_count": 145},
    {"user_id": "U014", "username": "低调食家老李",   "user_level": 8, "vip_status": True,  "review_count": 891},
    {"user_id": "U015", "username": "杭州西湖边的鱼", "user_level": 6, "vip_status": False, "review_count": 198},
    {"user_id": "U016", "username": "粤菜情结",       "user_level": 7, "vip_status": True,  "review_count": 356},
    {"user_id": "U017", "username": "成都胖娃",       "user_level": 4, "vip_status": False, "review_count": 89},
    {"user_id": "U018", "username": "喜欢吃海鲜的人", "user_level": 5, "vip_status": False, "review_count": 167},
    {"user_id": "U019", "username": "深圳漂流记",     "user_level": 3, "vip_status": False, "review_count": 54},
    {"user_id": "U020", "username": "美食博主小红",   "user_level": 9, "vip_status": True,  "review_count": 2103},
    {"user_id": "U021", "username": "下班觅食",       "user_level": 2, "vip_status": False, "review_count": 31},
    {"user_id": "U022", "username": "职业点评人",     "user_level": 8, "vip_status": True,  "review_count": 734},
    {"user_id": "U023", "username": "享受慢生活",     "user_level": 4, "vip_status": False, "review_count": 76},
    {"user_id": "U024", "username": "北漂吃货联盟",   "user_level": 6, "vip_status": True,  "review_count": 312},
    {"user_id": "U025", "username": "广东人爱喝汤",   "user_level": 7, "vip_status": False, "review_count": 423},
    {"user_id": "U026", "username": "辣度五颗星",     "user_level": 5, "vip_status": False, "review_count": 188},
    {"user_id": "U027", "username": "寿司控阿强",     "user_level": 6, "vip_status": True,  "review_count": 267},
    {"user_id": "U028", "username": "养生食堂",       "user_level": 4, "vip_status": False, "review_count": 92},
    {"user_id": "U029", "username": "穷游美食家",     "user_level": 3, "vip_status": False, "review_count": 48},
    {"user_id": "U030", "username": "米其林追星族",   "user_level": 8, "vip_status": True,  "review_count": 654},
    {"user_id": "U031", "username": "外卖重度用户",   "user_level": 2, "vip_status": False, "review_count": 19},
    {"user_id": "U032", "username": "热爱生活的老张", "user_level": 5, "vip_status": True,  "review_count": 201},
    {"user_id": "U033", "username": "吃个够",         "user_level": 3, "vip_status": False, "review_count": 63},
    {"user_id": "U034", "username": "公司团建专家",   "user_level": 6, "vip_status": False, "review_count": 143},
    {"user_id": "U035", "username": "约会餐厅侦探",   "user_level": 7, "vip_status": True,  "review_count": 378},
]

# ──────────────────────────────────────────────────────────────
# 85 条评论模板（正/负/中性，覆盖各菜系、堂食/外卖）
# ──────────────────────────────────────────────────────────────
TEMPLATES = [
    # ═══ 火锅 正面 ════════════════════════════════════════════
    {"content":"服务真的没话说！服务员全程关注桌面，锅底味道浓郁，鸭血和毛肚是必点。排了将近40分钟，但完全值得，下次还会来！",
     "score":5,"score_text":"口味5.0|环境4.8|服务5.0","dishes":"鸭血|毛肚|菌汤锅底","order_type":"堂食","sentiment":"positive",
     "aspects":[("服务","很好"),("口味","浓郁"),("等待","较长")]},
    {"content":"海底捞永远是行业标杆，小料台种类超多，生日当天还有惊喜小蛋糕，牛肉片非常新鲜，性价比挺高。",
     "score":5,"score_text":"口味5.0|环境5.0|服务5.0","dishes":"牛肉片|鸳鸯锅","order_type":"堂食","sentiment":"positive",
     "aspects":[("服务","标杆"),("新鲜度","很新鲜"),("性价比","高")]},
    {"content":"提前预约顺利入座，番茄锅底清甜，食材很新鲜，服务态度超好，全程帮忙照料，感动！",
     "score":5,"score_text":"口味4.9|环境4.8|服务5.0","dishes":"番茄锅底|鲜虾|脑花","order_type":"堂食","sentiment":"positive",
     "aspects":[("服务","超好"),("食材","新鲜"),("等待","无需")]},
    {"content":"第一次来就被惊艳了！羊肉卷超薄，入锅就熟，锅底香气十足，服务员手速一流，火锅界天花板！",
     "score":5,"score_text":"口味5.0|环境4.9|服务5.0","dishes":"羊肉卷|猪脑|宽粉","order_type":"堂食","sentiment":"positive",
     "aspects":[("食材","新鲜"),("服务速度","很快"),("口味","天花板")]},
    {"content":"家庭聚餐选这里绝对没错，包间宽敞，锅底种类多，孜然锅底是惊喜，服务全程跟进，父母很满意。",
     "score":4,"score_text":"口味4.8|环境4.5|服务5.0","dishes":"孜然锅底|毛肚|牛百叶","order_type":"堂食","sentiment":"positive",
     "aspects":[("环境","宽敞"),("服务","周到"),("口味","丰富")]},
    # 火锅 负面
    {"content":"等了快两小时才进去，服务员态度还一般，鲜切羊肉催了三次才上来，感觉已经失去当初水准，价格还涨了。",
     "score":2,"score_text":"口味3.0|环境3.5|服务2.0","dishes":"鲜切羊肉","order_type":"堂食","sentiment":"negative",
     "aspects":[("等待","太长"),("服务","一般"),("上菜速度","慢"),("价格","涨了")]},
    {"content":"食材不新鲜，毛肚有异味，反映给服务员被无视，账单还多了一道菜，沟通半天才退，体验极差。",
     "score":1,"score_text":"口味1.5|环境3.0|服务1.0","dishes":"毛肚","order_type":"堂食","sentiment":"negative",
     "aspects":[("新鲜度","不新鲜"),("服务态度","差"),("账单","有误")]},
    {"content":"价格越来越贵，128一位的套餐料很少，汤底味道淡，完全不值这个价，以后不来了。",
     "score":2,"score_text":"口味2.5|环境4.0|服务3.0","dishes":"套餐锅底","order_type":"堂食","sentiment":"negative",
     "aspects":[("价格","贵"),("分量","少"),("性价比","低")]},
    {"content":"节假日人太多了，上菜特别慢，等了50分钟才到，食材已经不新鲜，浪费了大半天时间，失望透顶。",
     "score":2,"score_text":"口味2.0|环境3.0|服务2.5","dishes":"鸭肠|虾滑","order_type":"堂食","sentiment":"negative",
     "aspects":[("等待","太长"),("上菜","极慢"),("食材","不新鲜")]},
    # ═══ 川菜 正面 ════════════════════════════════════════════
    {"content":"正宗川菜！回锅肉肥而不腻，麻婆豆腐麻辣鲜香，口水鸡配料丰富。价格公道，家庭聚餐首选，停车方便，常来！",
     "score":5,"score_text":"口味5.0|环境4.2|服务4.5","dishes":"回锅肉|麻婆豆腐|口水鸡","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","正宗"),("价格","公道"),("停车","方便")]},
    {"content":"水煮鱼片鲜嫩入味，辣度刚好，鱼肉没有腥味，汤底可以蘸饼吃，超满足。分量很足，两个人吃撑了。",
     "score":5,"score_text":"口味5.0|环境4.3|服务4.4","dishes":"水煮鱼|蒜苔炒肉|蒸蛋","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","入味"),("分量","足"),("新鲜度","很好")]},
    {"content":"夫妻肺片做得非常地道，花椒味十足，辣而不燥。服务员推荐了一道招牌干锅虾，果然没让我失望，下次还点！",
     "score":5,"score_text":"口味5.0|环境4.0|服务4.5","dishes":"夫妻肺片|干锅虾","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","地道"),("服务","推荐准确"),("辣度","刚好")]},
    {"content":"成都本地人告诉我的宝藏店，兔头、夫妻肺片、麻辣香锅都很在线，价格实惠，本地人多，放心吃！",
     "score":4,"score_text":"口味4.8|环境3.8|服务4.2","dishes":"兔头|麻辣香锅|夫妻肺片","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","地道"),("性价比","高"),("人气","旺")]},
    # 川菜 负面
    {"content":"菜品温度不够，上来就是凉的，麻婆豆腐味道很淡，一点辣味都没有，跟正宗川菜差距大。价格还不便宜。",
     "score":2,"score_text":"口味2.0|环境3.5|服务3.0","dishes":"麻婆豆腐","order_type":"堂食","sentiment":"negative",
     "aspects":[("温度","凉了"),("口味","太淡"),("性价比","低")]},
    {"content":"点了外卖，包装差，汤都洒了一半，还漏掉一道菜。联系商家说下次补，再也没有下次，差评！",
     "score":1,"score_text":"口味3.0|服务1.0","dishes":"水煮鱼|蒜苔炒肉","order_type":"外卖","sentiment":"negative",
     "aspects":[("包装","差"),("配送","漏送"),("售后","差")]},
    {"content":"油太多了，吃了很腻，锅里全是辣椒油，菜根本看不见。服务员催单催得很烦，体验很不好。",
     "score":2,"score_text":"口味2.5|环境3.0|服务2.0","dishes":"干锅花菜|辣子鸡","order_type":"堂食","sentiment":"negative",
     "aspects":[("油腻","很腻"),("服务","催单"),("口味","过重")]},
    # 川菜 中性
    {"content":"味道整体还可以，菜品种类丰富，就是等待时间有点长，性价比一般，相比同类店贵一些，但服务确实到位。",
     "score":3,"score_text":"口味4.0|环境3.5|服务4.5","dishes":"涮羊肉|豆腐脑","order_type":"堂食","sentiment":"neutral",
     "aspects":[("口味","还可以"),("等待","较长"),("价格","偏贵")]},
    {"content":"朋友推荐来的，口味中规中矩，装修有点旧，但服务还算热情。适合家庭聚餐，周末建议提前预约。",
     "score":3,"score_text":"口味3.5|环境3.0|服务3.8","dishes":"回锅肉|蒜苗炒腊肉","order_type":"堂食","sentiment":"neutral",
     "aspects":[("口味","中规中矩"),("环境","旧"),("服务","热情")]},
    # ═══ 日料 正面 ════════════════════════════════════════════
    {"content":"环境非常精致，灯光恰到好处，三文鱼刺身新鲜度极高，厚切入口即化，服务专业有礼，清酒搭配绝！稍贵但物有所值。",
     "score":5,"score_text":"口味5.0|环境5.0|服务4.8","dishes":"三文鱼刺身|厚切金枪鱼|清酒","order_type":"堂食","sentiment":"positive",
     "aspects":[("环境","精致"),("新鲜度","极高"),("服务","专业")]},
    {"content":"午市套餐128元，含刺身拼盘、茶碗蒸、味噌汤，量足且新鲜，性价比超高，周末要提前订位！",
     "score":5,"score_text":"口味4.8|环境4.5|服务4.5","dishes":"刺身拼盘|茶碗蒸|味噌汤","order_type":"堂食","sentiment":"positive",
     "aspects":[("性价比","高"),("新鲜度","新鲜"),("分量","足")]},
    {"content":"约会圣地！包厢私密，烤物火候精准，和牛入口即化，清酒侍者推荐很准。服务极佳，已经是第三次来了。",
     "score":5,"score_text":"口味5.0|环境5.0|服务5.0","dishes":"和牛烧烤|清酒|乌冬面","order_type":"堂食","sentiment":"positive",
     "aspects":[("环境","私密"),("口味","极佳"),("服务","贴心")]},
    {"content":"鲷鱼船饭超推荐！现做现吃，鱼肉鲜嫩，酱汁搭配绝妙，价格在日料里算合理。店里人不多，等位很快。",
     "score":4,"score_text":"口味4.9|环境4.3|服务4.4","dishes":"鲷鱼船饭|味增汤","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","鲜嫩"),("等位","快"),("价格","合理")]},
    # 日料 负面
    {"content":"刺身不新鲜，三文鱼颜色暗淡，吃了有点腥味。价格很高但质量不配，服务员不主动，续茶要等很久。",
     "score":2,"score_text":"口味2.0|环境3.8|服务2.5","dishes":"三文鱼刺身|海胆","order_type":"堂食","sentiment":"negative",
     "aspects":[("新鲜度","不新鲜"),("价格","贵"),("服务","被动")]},
    {"content":"网红店名不副实，图片和实物差距大，料太少，份量小，120元的拼盘只有5种，失望。",
     "score":2,"score_text":"口味3.0|环境4.0|服务3.5","dishes":"刺身拼盘|手卷","order_type":"堂食","sentiment":"negative",
     "aspects":[("性价比","低"),("分量","少"),("图片","和实物不符")]},
    # ═══ 粤菜/早茶 正面 ══════════════════════════════════════
    {"content":"广州早茶天花板！虾饺皮薄馅足，叉烧包烤色金黄，肠粉滑嫩弹牙，配茶刚刚好，服务阿姨很亲切。",
     "score":5,"score_text":"口味5.0|环境4.8|服务4.8","dishes":"虾饺|叉烧包|肠粉|普洱茶","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","天花板"),("分量","足"),("服务","亲切")]},
    {"content":"百年老字号，值得信赖！烧鹅皮脆肉嫩，白切鸡蘸姜葱蒜超香，老火靓汤喝了暖胃。强烈推荐给来广州的朋友。",
     "score":5,"score_text":"口味5.0|环境4.5|服务4.6","dishes":"烧鹅|白切鸡|老火靓汤","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","地道"),("品质","高"),("推荐","给外地人")]},
    {"content":"陶陶居的点心种类超多，推车服务很有仪式感，煎萝卜糕外脆内软，糯米鸡香气扑鼻，性价比不错。",
     "score":4,"score_text":"口味4.7|环境4.5|服务4.4","dishes":"煎萝卜糕|糯米鸡|虾饺皇","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","香"),("种类","多"),("性价比","不错")]},
    {"content":"来广州必打卡！广州酒家的虾饺皇是招牌，皮透薄，虾仁脆弹，配当地茶特别对味，来了三次了！",
     "score":5,"score_text":"口味5.0|环境4.6|服务4.7","dishes":"虾饺皇|蛋挞|马拉糕","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","招牌"),("必打卡","是"),("回头率","高")]},
    # 粤菜 负面
    {"content":"上菜奇慢，等了40分钟点心还没来，催了两次服务员才说排队。口感一般，虾饺皮太厚，失去了粤点精髓。",
     "score":2,"score_text":"口味2.5|环境3.5|服务2.0","dishes":"虾饺|肠粉","order_type":"堂食","sentiment":"negative",
     "aspects":[("上菜速度","慢"),("口感","一般"),("服务","差")]},
    {"content":"味道偷工减料，和十年前差很多，叉烧肉质干柴，价格却涨了50%，老字号沦落了，心疼。",
     "score":2,"score_text":"口味2.0|环境3.8|服务3.5","dishes":"叉烧包|肠粉","order_type":"堂食","sentiment":"negative",
     "aspects":[("口味","下滑"),("性价比","低"),("品质","退步")]},
    # ═══ 烤鸭 正面 ════════════════════════════════════════════
    {"content":"便宜坊烤鸭真的是北京必吃！皮脆肉嫩，片鸭师傅刀工精湛，配荷叶饼、葱丝和甜面酱完美，百年老店名不虚传。",
     "score":5,"score_text":"口味5.0|环境4.5|服务4.5","dishes":"烤鸭|荷叶饼|葱丝","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","完美"),("刀工","精湛"),("老字号","值得信赖")]},
    {"content":"烤鸭皮酥脆，油脂丰富，鸭肉不柴，烤制火候把握得很好。服务到位，环境古朴，北京朋友强烈推荐。",
     "score":5,"score_text":"口味4.9|环境4.4|服务4.6","dishes":"烤鸭|鸭架汤","order_type":"堂食","sentiment":"positive",
     "aspects":[("皮","酥脆"),("口味","丰富"),("服务","到位")]},
    # 烤鸭 中性/负面
    {"content":"环境宽敞，但服务慢，等了20分钟才有人来点菜。烤鸭口感一般，比不上全聚德，但价格便宜些。",
     "score":3,"score_text":"口味3.5|环境4.2|服务3.0","dishes":"烤鸭","order_type":"堂食","sentiment":"neutral",
     "aspects":[("服务","慢"),("口味","一般"),("价格","便宜")]},
    {"content":"烤鸭偏咸，皮不够脆，鸭肉有些发硬，片鸭师傅新手感强，片得不均匀。性价比一般，不推荐。",
     "score":2,"score_text":"口味2.5|环境3.8|服务3.0","dishes":"烤鸭|鸭肝","order_type":"堂食","sentiment":"negative",
     "aspects":[("口味","偏咸"),("皮","不脆"),("刀工","差")]},
    # ═══ 面食/小吃 正面 ══════════════════════════════════════
    {"content":"炸酱面是一绝！酱香浓郁，面条筋道，配菜齐全，分量很大，一碗就够。服务效率高，地道的北京味儿！",
     "score":4,"score_text":"口味5.0|环境3.5|服务4.0","dishes":"老北京炸酱面|芥末墩","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","正宗"),("分量","足"),("服务","高效")]},
    {"content":"豆汁焦圈是北京特色，一开始接受不了，多喝几口就上瘾了！卤煮也很香，这才是真正的北京早餐。",
     "score":4,"score_text":"口味4.5|环境3.8|服务4.0","dishes":"豆汁|焦圈|卤煮","order_type":"堂食","sentiment":"positive",
     "aspects":[("特色","地道"),("口味","独特"),("体验","好")]},
    {"content":"龙抄手的皮薄馅鲜，汤底清甜，红油钞手辣而不燥。价格亲民，来成都不打卡太可惜了！",
     "score":5,"score_text":"口味5.0|环境4.0|服务4.3","dishes":"红油抄手|清汤抄手|赖汤圆","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","鲜"),("价格","亲民"),("必打卡","是")]},
    {"content":"大壶春生煎皮薄汁多，底部煎得金黄焦脆，一口下去满嘴油香，配上辣酱绝了，排队也值得！",
     "score":5,"score_text":"口味5.0|环境3.5|服务4.2","dishes":"生煎包|辣酱","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","极好"),("皮","酥脆"),("汁水","丰富")]},
    {"content":"知味观小笼包皮薄汤汁足，一口一个超满足。葱包烩也很有特色，杭州必吃，价格接受度高。",
     "score":4,"score_text":"口味4.8|环境4.2|服务4.3","dishes":"小笼包|葱包烩","order_type":"堂食","sentiment":"positive",
     "aspects":[("汤汁","足"),("口味","很好"),("价格","合理")]},
    # 面食/小吃 负面
    {"content":"面条煮过头了，软塌塌没有嚼劲，炸酱太淡，菜码里的黄瓜好像不新鲜，有点异味，失望。",
     "score":2,"score_text":"口味2.0|环境3.5|服务3.5","dishes":"炸酱面","order_type":"堂食","sentiment":"negative",
     "aspects":[("口感","过软"),("口味","淡"),("新鲜度","有问题")]},
    {"content":"生煎不新鲜，底部焦过头了，有点苦味，汁水也少，和网上说的相差太多，踩坑了。",
     "score":2,"score_text":"口味2.0|环境3.8|服务3.5","dishes":"生煎包","order_type":"堂食","sentiment":"negative",
     "aspects":[("新鲜度","不新鲜"),("口感","苦"),("汁水","少")]},
    # ═══ 海鲜 正面 ════════════════════════════════════════════
    {"content":"海鲜超新鲜！皮皮虾肥美，蒜蓉蒸扇贝香而不腻，价格透明按斤算，老板实在，下次还来。",
     "score":5,"score_text":"口味5.0|环境4.0|服务4.5","dishes":"皮皮虾|蒜蓉扇贝|白灼基围虾","order_type":"堂食","sentiment":"positive",
     "aspects":[("新鲜度","极新鲜"),("价格","透明"),("口味","鲜美")]},
    {"content":"渔港直供，螃蟹肥美，蒸出来黄多肉紧，就是要早来，下午就卖完了。桌子简陋但吃的是货真价实。",
     "score":4,"score_text":"口味4.8|环境3.2|服务3.8","dishes":"清蒸螃蟹|白灼虾","order_type":"堂食","sentiment":"positive",
     "aspects":[("新鲜度","很高"),("性价比","高"),("环境","简陋")]},
    # 海鲜 负面
    {"content":"海鲜价格虚高，斤两缩水严重，活鱼买时1.5斤称出来1斤，投诉被糊弄过去，不会再来了。",
     "score":1,"score_text":"口味3.5|服务1.0","dishes":"清蒸鲈鱼","order_type":"堂食","sentiment":"negative",
     "aspects":[("价格","欺诈"),("称重","不准"),("诚信","差")]},
    {"content":"海鲜不新鲜，生蚝闻起来有味道，反映后服务员说正常，太气了。深圳来消费的不是来受气的。",
     "score":1,"score_text":"口味1.5|服务1.5","dishes":"生蚝|皮皮虾","order_type":"堂食","sentiment":"negative",
     "aspects":[("新鲜度","不新鲜"),("服务态度","差"),("投诉处理","差")]},
    # ═══ 杭帮菜 正面 ═════════════════════════════════════════
    {"content":"楼外楼西湖醋鱼是一绝！鱼肉嫩滑，酸甜适口，还点了东坡肉，入口即化，配江南风格的环境，太美了！",
     "score":5,"score_text":"口味5.0|环境5.0|服务4.8","dishes":"西湖醋鱼|东坡肉|宋嫂鱼羹","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","一绝"),("环境","美"),("体验","完美")]},
    {"content":"外婆家性价比很高，藕粉、西湖醋鱼、东坡肉都好吃，排队要等，但值得。服务人员很热情。",
     "score":4,"score_text":"口味4.5|环境4.4|服务4.4","dishes":"西湖醋鱼|东坡肉|藕粉","order_type":"堂食","sentiment":"positive",
     "aspects":[("性价比","高"),("口味","不错"),("等待","值")]},
    {"content":"新荣记台州菜是真的高端！鱼生、敲鱼面、清蒸黄鱼，每一道都是精心打磨，食材无可挑剔，价格自然不菲但体验满分。",
     "score":5,"score_text":"口味5.0|环境5.0|服务5.0","dishes":"鱼生|敲鱼面|清蒸黄鱼","order_type":"堂食","sentiment":"positive",
     "aspects":[("食材","无可挑剔"),("口味","精湛"),("体验","满分")]},
    # 杭帮菜 中性/负面
    {"content":"西湖醋鱼味道一般，酸甜比例不协调，鱼肉有点腥。楼外楼名气大，但实际体验一般，更多是在消费情怀。",
     "score":3,"score_text":"口味3.2|环境4.5|服务4.0","dishes":"西湖醋鱼","order_type":"堂食","sentiment":"neutral",
     "aspects":[("口味","一般"),("情怀","有"),("性价比","一般")]},
    {"content":"排队一小时才进去，味道还可以但不算惊艳，东坡肉偏甜，对于口味偏清淡的北方人来说太甜了。",
     "score":3,"score_text":"口味3.5|环境4.2|服务3.8","dishes":"东坡肉|龙井虾仁","order_type":"堂食","sentiment":"neutral",
     "aspects":[("等待","长"),("口味","偏甜"),("地域","口味差异")]},
    # ═══ 外卖 正面 ════════════════════════════════════════════
    {"content":"外卖25分钟到！保温做得好，到手还是热的。麻辣香锅料足，辣度可以备注，强烈推荐，下次还会点！",
     "score":5,"score_text":"口味5.0|服务5.0","dishes":"麻辣香锅","order_type":"外卖","sentiment":"positive",
     "aspects":[("配送速度","很快"),("保温","好"),("分量","足")]},
    {"content":"连续点了一个月！粥品系列都好喝，食材新鲜，配送准时，打包规整，汤没洒。点外卖就认准这家了。",
     "score":5,"score_text":"口味5.0|服务5.0","dishes":"皮蛋瘦肉粥|虾饺","order_type":"外卖","sentiment":"positive",
     "aspects":[("口味","稳定"),("配送","准时"),("包装","好")]},
    {"content":"夜宵外卖选这家绝了！小龙虾辣度十足，虾肉饱满，份量够，凌晨1点还能送到，赞！",
     "score":5,"score_text":"口味5.0|服务5.0","dishes":"麻辣小龙虾|烤串","order_type":"外卖","sentiment":"positive",
     "aspects":[("口味","十足"),("配送","凌晨可送"),("分量","够")]},
    # 外卖 负面
    {"content":"外卖拖了90分钟还没到，打电话客服说路上堵，最后到手食物全凉了，汤洒了一半，要求退款被拒绝，投诉无门。",
     "score":1,"score_text":"口味2.0|服务1.0","dishes":"黄焖鸡米饭","order_type":"外卖","sentiment":"negative",
     "aspects":[("配送","极慢"),("温度","全凉"),("售后","差")]},
    {"content":"外卖重量明显缩水，点了三份套餐，实际到手两份半，客服推诿说是正常损耗，绝不再来。",
     "score":1,"score_text":"口味3.0|服务1.0","dishes":"套餐","order_type":"外卖","sentiment":"negative",
     "aspects":[("分量","缺斤少两"),("售后","差")]},
    # ═══ 综合中性 ═════════════════════════════════════════════
    {"content":"第一次来，朋友推荐的。味道还行，不算惊艳但也不差。环境装修普通，停车不便，下次可能考虑其他。",
     "score":3,"score_text":"口味3.5|环境3.0|服务3.5","dishes":"","order_type":"堂食","sentiment":"neutral",
     "aspects":[("口味","一般"),("环境","普通"),("停车","不便")]},
    {"content":"节假日人太多，上菜慢，但食物质量还不错。价格合理，适合周末家庭聚餐，排队是劣势。",
     "score":3,"score_text":"口味4.0|环境3.5|服务3.0","dishes":"","order_type":"堂食","sentiment":"neutral",
     "aspects":[("上菜","慢"),("食物","不错"),("排队","长")]},
    {"content":"性价比一般，菜量少，味道说得过去。朋友聚会来了一次，可以但不必须，找特别想来的机会再说。",
     "score":3,"score_text":"口味3.5|环境4.0|服务3.5","dishes":"","order_type":"堂食","sentiment":"neutral",
     "aspects":[("性价比","一般"),("分量","少"),("口味","说得过去")]},
    {"content":"环境不错，适合商务宴请，但菜价偏贵，性价比普通。味道中等偏上，服务还算专业。",
     "score":3,"score_text":"口味3.8|环境4.5|服务4.2","dishes":"","order_type":"堂食","sentiment":"neutral",
     "aspects":[("环境","好"),("价格","贵"),("服务","专业")]},
    # ═══ 额外长评（更真实感）════════════════════════════════
    {"content":"来了三次，每次体验都很稳定。招牌菜一直保持水准，服务员记得我的口味偏好，这种被认出来的感觉很好。唯一缺点是停车场太小，高峰期要绕几圈。总体满意，是家值得长期支持的老店。",
     "score":4,"score_text":"口味4.7|环境4.2|服务4.8","dishes":"招牌菜|米饭","order_type":"堂食","sentiment":"positive",
     "aspects":[("稳定性","高"),("服务","记住顾客"),("停车","难")]},
    {"content":"带外地朋友来打卡，朋友非常满意，直说终于吃到了真正的本地特色。菜品色香味俱全，摆盘精致，适合拍照发朋友圈。价格在当地算中等，综合来说很值！",
     "score":5,"score_text":"口味5.0|环境4.7|服务4.5","dishes":"特色菜|拍照菜","order_type":"堂食","sentiment":"positive",
     "aspects":[("地方特色","地道"),("摆盘","精致"),("适合打卡","是")]},
    {"content":"公司团建选这里，包间容纳20人没问题，提前沟通好菜单，服务配合度高，整体非常顺畅。菜品分量足，口味大众化，适合商务接待。下次还会继续合作。",
     "score":5,"score_text":"口味4.5|环境4.8|服务5.0","dishes":"宴会套餐|冷盘|汤品","order_type":"堂食","sentiment":"positive",
     "aspects":[("包间","宽敞"),("商务","适合"),("配合度","高")]},
    {"content":"已经不是第一次失望了。上次吃完觉得一般，这次带家人来，发现质量更差了。食材新鲜度下滑，分量减少，价格却上涨。感觉是在吃老本，不思进取，名气越大越让人失望，给个低分警示。",
     "score":2,"score_text":"口味2.5|环境3.5|服务3.0","dishes":"招牌菜","order_type":"堂食","sentiment":"negative",
     "aspects":[("新鲜度","下滑"),("分量","减少"),("价格","上涨"),("质量","退步")]},
    {"content":"朋友推荐说绝对不踩雷，结果我们点的几个菜都很普通。服务态度尚可，环境也还好，就是食物本身让我提不起兴趣。可能口味不合，但如果说必吃，我不认同，中规中矩而已。",
     "score":3,"score_text":"口味3.0|环境4.0|服务4.2","dishes":"","order_type":"堂食","sentiment":"neutral",
     "aspects":[("口味","普通"),("服务","尚可"),("推荐度","中等")]},
    # ═══ 额外单维度差评 ══════════════════════════════════════
    {"content":"服务极差！叫了四次服务员才来，态度傲慢，点菜完全不记，上错了还不道歉，这种态度让人无法接受。",
     "score":2,"score_text":"口味4.0|服务1.0","dishes":"","order_type":"堂食","sentiment":"negative",
     "aspects":[("服务态度","傲慢"),("响应","慢")]},
    {"content":"环境太嘈杂了，旁边一桌在大声喧哗，服务员完全不干预。音乐声音也很大，无法正常交流，进来二十分钟就走了。",
     "score":2,"score_text":"口味3.5|环境1.5|服务2.5","dishes":"","order_type":"堂食","sentiment":"negative",
     "aspects":[("噪音","很大"),("环境","嘈杂"),("干预","无")]},
    {"content":"卫生状况堪忧！桌子有油污没擦干净，筷子有污渍，厕所也很脏，这种卫生条件根本不应该开门。",
     "score":1,"score_text":"口味3.0|环境1.0|服务2.0","dishes":"","order_type":"堂食","sentiment":"negative",
     "aspects":[("卫生","差"),("桌面","脏"),("厕所","脏")]},
    # ═══ 额外单维度好评 ══════════════════════════════════════
    {"content":"菜品卖相一般但味道绝！隐藏在小巷里的宝藏店，本地人才知道，不被流量带跑，纯靠口味征服回头客。",
     "score":5,"score_text":"口味5.0|环境3.5|服务4.2","dishes":"家常菜|腊味","order_type":"堂食","sentiment":"positive",
     "aspects":[("口味","绝"),("宝藏店","是"),("回头客","多")]},
    {"content":"停车超方便，有专属停车场，而且是免费的！光这一点在市中心就已经非常加分了，东西也好吃，值得一来。",
     "score":4,"score_text":"口味4.5|环境4.3|服务4.3","dishes":"","order_type":"堂食","sentiment":"positive",
     "aspects":[("停车","免费且方便"),("口味","好")]},
    {"content":"给老人过生日来的，包间布置很温馨，还送了长寿面，服务员唱生日歌，老人很开心，感动全家！",
     "score":5,"score_text":"口味4.5|环境5.0|服务5.0","dishes":"长寿面|生日蛋糕","order_type":"堂食","sentiment":"positive",
     "aspects":[("生日服务","周到"),("氛围","温馨"),("体验","感动")]},
    {"content":"点了打包带走，包装很严实，汤类用密封袋，干湿分离，一滴没漏。这种用心的包装在外卖届很少见，好评！",
     "score":5,"score_text":"口味4.8|服务5.0","dishes":"煲汤|蒸菜","order_type":"打包","sentiment":"positive",
     "aspects":[("包装","精心"),("干湿分离","有"),("用心","感受到")]},
]

# 时间分布权重（晚餐高峰，深夜低谷）
HOUR_WEIGHTS = [1,1,1,1,1,1,2,3,5,5,6,8,10,10,8,6,4,5,10,12,10,8,5,3]


def _rand_time(days_back=730):
    day_off  = random.randint(0, days_back)
    hour     = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
    minute   = random.randint(0, 59)
    t = datetime.now() - timedelta(days=day_off, hours=hour, minutes=minute)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _make_review(shop, tpl, user, idx):
    rid = hashlib.md5(f"{shop['shop_id']}{user['user_id']}{idx}".encode()).hexdigest()[:16]
    images = []
    if random.random() < 0.42:
        images = [f"https://p0.meituan.net/food/sample_{random.randint(1000,9999)}.jpg"
                  for _ in range(random.randint(1, 5))]
    return {
        "review_id":      rid,
        "shop_id":        shop["shop_id"],
        "shop_name":      shop["shop_name"],
        "platform":       shop["platform"],
        "category":       shop.get("category",""),
        "city":           shop.get("city",""),
        "district":       shop.get("district",""),
        "user_id":        user["user_id"],
        "username":       user["username"],
        "user_level":     user["user_level"],
        "vip_status":     user["vip_status"],
        "review_content": tpl["content"],
        "review_score":   tpl["score"],
        "score_text":     tpl.get("score_text",""),
        "review_time":    _rand_time(),
        "like_count":     max(0, int(random.expovariate(0.2))),
        "reply_count":    random.choices([0,1,2,3], weights=[65,20,10,5])[0],
        "order_type":     tpl.get("order_type","堂食"),
        "dishes":         tpl.get("dishes",""),
        "images":         "|".join(images),
        "sentiment_label":{"positive":1,"negative":-1,"neutral":0}[tpl["sentiment"]],
        "sentiment":      tpl["sentiment"],
        "absa_aspects":   json.dumps(
            [{"aspect":a,"opinion":o} for a,o in tpl.get("aspects",[])],
            ensure_ascii=False),
        "crawl_time":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate(n=1000):
    os.makedirs("data", exist_ok=True)

    # 按店铺评分分布分配评论量（高评分店铺评论更多）
    scores = [s["score"] for s in SHOPS]
    total_score = sum(scores)
    shop_weights = [sc / total_score for sc in scores]

    reviews = []
    for i in range(n):
        shop = random.choices(SHOPS, weights=shop_weights)[0]
        # 匹配菜系相关模板（提高真实度）
        cat = shop.get("category","")
        if cat in ("火锅",):
            pool = [t for t in TEMPLATES if any(d in t["dishes"] for d in ["锅","毛肚","鸭血","羊肉","脑花"])]
        elif cat in ("川菜","串串香"):
            pool = [t for t in TEMPLATES if any(k in t["content"] for k in ["川","辣","麻","串"])]
        elif cat in ("粤菜","海鲜"):
            pool = [t for t in TEMPLATES if any(k in t["content"] for k in ["粤","海鲜","点心","虾饺","烧鹅","白切"])]
        elif cat in ("日料",):
            pool = [t for t in TEMPLATES if any(k in t["content"] for k in ["日料","刺身","寿司","清酒","和牛"])]
        elif cat in ("烤鸭",):
            pool = [t for t in TEMPLATES if "烤鸭" in t["content"]]
        elif cat in ("杭帮菜","台州菜"):
            pool = [t for t in TEMPLATES if any(k in t["content"] for k in ["杭","西湖","东坡","龙井","楼外"])]
        elif cat in ("小吃",):
            pool = [t for t in TEMPLATES if any(k in t["content"] for k in ["小笼","生煎","炸酱面","抄手","豆汁","焦圈"])]
        else:
            pool = TEMPLATES
        if not pool:
            pool = TEMPLATES
        tpl  = random.choice(pool)
        user = random.choice(USERS)
        reviews.append(_make_review(shop, tpl, user, i))

    reviews.sort(key=lambda x: x["review_time"], reverse=True)

    fields = ["review_id","shop_id","shop_name","platform","category","city","district",
              "user_id","username","user_level","vip_status",
              "review_content","review_score","score_text","review_time",
              "like_count","reply_count","order_type","dishes","images",
              "sentiment_label","sentiment","absa_aspects","crawl_time"]

    csv_path = "data/sample_reviews.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(reviews)

    shops_path = "data/sample_shops.csv"
    shop_fields = ["shop_id","shop_name","platform","category","city","district",
                   "address","average_price","score","taste_score",
                   "environment_score","service_score","review_count","tags"]
    with open(shops_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=shop_fields, extrasaction="ignore")
        w.writeheader(); w.writerows(SHOPS)

    pos = sum(1 for r in reviews if r["sentiment"]=="positive")
    neg = sum(1 for r in reviews if r["sentiment"]=="negative")
    neu = sum(1 for r in reviews if r["sentiment"]=="neutral")
    cities = len({s["city"] for s in SHOPS})

    print(f"\n数据生成完成")
    print(f"  评论总数: {len(reviews)}")
    print(f"  店铺数量: {len(SHOPS)} 家 / {cities} 个城市")
    print(f"  情感分布: 正面 {pos}({pos/n*100:.0f}%) 负面 {neg}({neg/n*100:.0f}%) 中性 {neu}({neu/n*100:.0f}%)")
    print(f"  输出文件: {csv_path}")
    print(f"            {shops_path}")


if __name__ == "__main__":
    generate(n=1000)
