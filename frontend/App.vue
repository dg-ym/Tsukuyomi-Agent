<script>
	export default {
		onLaunch: function() {
			const token = uni.getStorageSync('token')
			if (token && isTokenValid(token)) {
				// 已登录，直接进入 main
				uni.reLaunch({ url: '/pages/main' })
			}
		},
		onShow: function() {
			console.log('App Show')
		},
		onHide: function() {
			console.log('App Hide')
		}
	}

	function isTokenValid(token) {
		try {
			const payload = JSON.parse(atob(token.split('.')[1]))
			return payload.exp * 1000 > Date.now()
		} catch {
			uni.removeStorageSync('token')
			return false
		}
	}
</script>

<style>
	html, body, #app { height: 100%; margin: 0; padding: 0; overflow: hidden; }
</style>
