const config = require('./config')

App({
  globalData: {
    openid: null
  },

  onLaunch() {
    if (!wx.cloud) {
      console.error('当前基础库不支持云能力，请把开发者工具的基础库调到 2.2.3 以上')
      return
    }
    wx.cloud.init({
      env: config.cloudEnv,
      traceUser: true
    })
    this.ensureLogin()
  },

  // 获取并缓存当前用户的 openid，用于判断商品是否属于自己
  ensureLogin() {
    return wx.cloud
      .callFunction({ name: 'login' })
      .then(res => {
        this.globalData.openid = res.result.openid
        return res.result.openid
      })
      .catch(err => {
        console.error('login 云函数调用失败，请确认已部署 login 云函数', err)
        return null
      })
  }
})
