const app = getApp()
const db = wx.cloud.database()
const CONDITIONS = ['全新', '9成新', '8成新', '7成新及以下']

Page({
  data: {
    images: [],
    title: '',
    price: '',
    conditions: CONDITIONS,
    conditionIndex: 0,
    desc: '',
    contact: '',
    submitting: false
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value })
  },

  onConditionChange(e) {
    this.setData({ conditionIndex: Number(e.detail.value) })
  },

  chooseImage() {
    const remain = 9 - this.data.images.length
    if (remain <= 0) {
      wx.showToast({ title: '最多上传 9 张', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: remain,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: res => {
        const paths = res.tempFiles.map(f => f.tempFilePath)
        this.setData({ images: this.data.images.concat(paths) })
      }
    })
  },

  removeImage(e) {
    const images = this.data.images.slice()
    images.splice(e.currentTarget.dataset.index, 1)
    this.setData({ images })
  },

  uploadAll() {
    const openid = app.globalData.openid || 'anon'
    const tasks = this.data.images.map((path, i) => {
      const match = /\.(\w+)$/.exec(path)
      const ext = match ? match[1] : 'jpg'
      const cloudPath = `products/${openid}_${Date.now()}_${i}.${ext}`
      return wx.cloud.uploadFile({ cloudPath, filePath: path }).then(r => r.fileID)
    })
    return Promise.all(tasks)
  },

  submit() {
    if (this.data.submitting) return

    const title = this.data.title.trim()
    const contact = this.data.contact.trim()
    const price = Number(this.data.price)

    if (this.data.images.length === 0) {
      return wx.showToast({ title: '请至少上传一张照片', icon: 'none' })
    }
    if (!title) {
      return wx.showToast({ title: '请填写标题', icon: 'none' })
    }
    if (this.data.price === '' || isNaN(price) || price < 0) {
      return wx.showToast({ title: '请填写正确的价格', icon: 'none' })
    }
    if (!contact) {
      return wx.showToast({ title: '请填写联系方式', icon: 'none' })
    }

    this.setData({ submitting: true })
    wx.showLoading({ title: '发布中...', mask: true })

    this.uploadAll()
      .then(fileIDs =>
        db.collection('products').add({
          data: {
            title,
            price,
            condition: this.data.conditions[this.data.conditionIndex],
            desc: this.data.desc.trim(),
            contact,
            images: fileIDs,
            status: 'available',
            createTime: db.serverDate()
          }
        })
      )
      .then(() => {
        wx.hideLoading()
        this.setData({ submitting: false })
        wx.showToast({ title: '发布成功' })
        setTimeout(() => {
          const pages = getCurrentPages()
          if (pages.length > 1) {
            wx.navigateBack()
          } else {
            wx.switchTab({ url: '/pages/index/index' })
          }
        }, 700)
      })
      .catch(err => {
        console.error(err)
        wx.hideLoading()
        this.setData({ submitting: false })
        wx.showToast({ title: '发布失败，请重试', icon: 'none' })
      })
  }
})
