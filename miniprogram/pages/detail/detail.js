const app = getApp()
const db = wx.cloud.database()

Page({
  data: {
    product: null,
    isOwner: false,
    loading: true
  },

  onLoad(options) {
    this.id = options.id
    if (app.globalData.openid) {
      this.fetch()
    } else {
      app.ensureLogin().then(() => this.fetch())
    }
  },

  fetch() {
    db.collection('products')
      .doc(this.id)
      .get()
      .then(res => {
        const product = res.data
        this.setData({
          product,
          isOwner: product._openid === app.globalData.openid,
          loading: false
        })
      })
      .catch(err => {
        console.error(err)
        this.setData({ loading: false })
        wx.showToast({ title: '商品不存在或已删除', icon: 'none' })
      })
  },

  previewImage(e) {
    const urls = this.data.product.images
    wx.previewImage({
      current: urls[e.currentTarget.dataset.index],
      urls
    })
  },

  copyContact() {
    wx.setClipboardData({
      data: this.data.product.contact,
      success: () => wx.showToast({ title: '联系方式已复制' })
    })
  },

  updateStatus(status, tip) {
    db.collection('products')
      .doc(this.id)
      .update({ data: { status } })
      .then(() => {
        wx.showToast({ title: tip })
        this.fetch()
      })
      .catch(err => {
        console.error(err)
        wx.showToast({ title: '操作失败', icon: 'none' })
      })
  },

  markSold() {
    wx.showModal({
      title: '标记已售出',
      content: '确定这件已经卖出去了吗？',
      success: r => {
        if (r.confirm) this.updateStatus('sold', '已标记售出')
      }
    })
  },

  markAvailable() {
    this.updateStatus('available', '已恢复在售')
  },

  remove() {
    wx.showModal({
      title: '删除',
      content: '删除后无法恢复，确定删除吗？',
      confirmColor: '#e64340',
      success: r => {
        if (!r.confirm) return
        const fileList = this.data.product.images || []
        const removeDoc = () =>
          db.collection('products')
            .doc(this.id)
            .remove()
            .then(() => {
              wx.showToast({ title: '已删除' })
              setTimeout(() => this.back(), 600)
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
  },

  back() {
    const pages = getCurrentPages()
    if (pages.length > 1) {
      wx.navigateBack()
    } else {
      wx.switchTab({ url: '/pages/index/index' })
    }
  },

  onShareAppMessage() {
    const p = this.data.product || {}
    return {
      title: p.title ? `${p.title}  ¥${p.price}` : '宝宝闲置好物',
      path: `/pages/detail/detail?id=${this.id}`,
      imageUrl: (p.images && p.images[0]) || ''
    }
  }
})
