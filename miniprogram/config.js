// 填你在「微信开发者工具 → 云开发」里创建的环境 ID（形如 baby-resale-2xxxxx）。
// ownerOpenid 填你自己的 openid：第一次跑起来后看控制台里 login 云函数返回的 openid，
// 复制过来。只有它匹配时，才会显示「标记已售 / 删除」等管理按钮（买家看不到）。
module.exports = {
  cloudEnv: 'REPLACE_WITH_YOUR_CLOUD_ENV_ID',
  ownerOpenid: 'REPLACE_WITH_YOUR_OPENID'
}
