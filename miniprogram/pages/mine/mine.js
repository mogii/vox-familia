const app = getApp()
const config = require('../../config')
const db = wx.cloud.database()

Page({
  data: {
    products: [],
    loading: false,
    isOwner: false
  },

  onShow() {
    this.load()
  },

  load() {
    const run = () => {
      this.setData({
        loading: true,
        isOwner: !!app.globalData.openid && app.globalData.openid === config.ownerOpenid
      })
      db.collection('products')
        .orderBy('createTime', 'desc')
        .limit(100)
        .get()
        .then(res => {
          this.setData({ products: res.data, loading: false })
          wx.stopPullDownRefresh()
        })
        .catch(err => {
          console.error(err)
          this.setData({ loading: false })
          wx.stopPullDownRefresh()
          wx.showToast({ title: '加载失败', icon: 'none' })
        })
    }

    if (app.globalData.openid) {
      run()
    } else {
      app.ensureLogin().then(run)
    }
  },

  onPullDownRefresh() {
    this.load()
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/detail/detail?id=${e.currentTarget.dataset.id}` })
  },

  updateStatus(id, status, tip) {
    db.collection('products')
      .doc(id)
      .update({ data: { status } })
      .then(() => {
        wx.showToast({ title: tip })
        this.load()
      })
      .catch(err => {
        console.error(err)
        wx.showToast({ title: '操作失败', icon: 'none' })
      })
  },

  markSold(e) {
    this.updateStatus(e.currentTarget.dataset.id, 'sold', '已标记售出')
  },

  markAvailable(e) {
    this.updateStatus(e.currentTarget.dataset.id, 'available', '已恢复在售')
  },

  remove(e) {
    const id = e.currentTarget.dataset.id
    const fileList = e.currentTarget.dataset.images || []
    wx.showModal({
      title: '删除',
      content: '删除后无法恢复，确定删除吗？',
      confirmColor: '#e64340',
      success: r => {
        if (!r.confirm) return
        const removeDoc = () =>
          db.collection('products')
            .doc(id)
            .remove()
            .then(() => {
              wx.showToast({ title: '已删除' })
              this.load()
            })
            .catch(err => {
              console.error(err)
              wx.showToast({ title: '删除失败', icon: 'none' })
            })

        if (fileList.length) {
          wx.cloud.deleteFile({ fileList }).then(removeDoc).catch(removeDoc)
        } else {
          removeDoc()
        }
      }
    })
  }
})
