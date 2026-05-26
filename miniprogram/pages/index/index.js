const PAGE_SIZE = 20
const db = wx.cloud.database()

Page({
  data: {
    products: [],
    loading: false,
    hasMore: true,
    page: 0
  },

  onShow() {
    // 每次回到首页都刷新，能看到新发布的、以及状态变化
    this.load(true)
  },

  load(reset) {
    if (this.data.loading) return
    if (!reset && !this.data.hasMore) return

    const page = reset ? 0 : this.data.page
    this.setData({ loading: true })

    db.collection('products')
      .where({ status: 'available' })
      .orderBy('createTime', 'desc')
      .skip(page * PAGE_SIZE)
      .limit(PAGE_SIZE)
      .get()
      .then(res => {
        const list = reset ? res.data : this.data.products.concat(res.data)
        this.setData({
          products: list,
          page: page + 1,
          hasMore: res.data.length === PAGE_SIZE,
          loading: false
        })
        wx.stopPullDownRefresh()
      })
      .catch(err => {
        console.error(err)
        this.setData({ loading: false })
        wx.stopPullDownRefresh()
        wx.showToast({ title: '加载失败，请检查云环境配置', icon: 'none' })
      })
  },

  onPullDownRefresh() {
    this.load(true)
  },

  onReachBottom() {
    this.load(false)
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/detail/detail?id=${e.currentTarget.dataset.id}` })
  },

  onShareAppMessage() {
    return {
      title: '我在卖宝宝闲置好物，快来挑挑看~',
      path: '/pages/index/index'
    }
  }
})
