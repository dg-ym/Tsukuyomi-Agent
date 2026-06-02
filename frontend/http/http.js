let BASE_URL = "http://127.0.0.1:8000";
if(process.env.NODE_ENV === "development"){
	BASE_URL = "http://127.0.0.1:8000"
}else{
	BASE_URL = "https://www.tukuyomi.com"
}

const request = (url,options) => {
	const token = uni.getStorageSync("token");
	return new Promise((resolve,reject) => {
		uni.request({
			url: BASE_URL + url,
			header:{
				"content-type": "application/json",
				"authorization": "Bearer " + token
			},
			...options,
			success: (res) => {
				const {statusCode, data} = res;
				if(statusCode == 200){
					resolve(data);
				}else if(statusCode === 401 || statusCode === 403){
					uni.removeStorageSync('token')
					uni.showToast({ title: '登录已过期，请重新登录', icon: 'none' })
					setTimeout(() => uni.redirectTo({ url: '/pages/login' }), 500)
					reject(new Error(data.detail || '未登录'))
				}else{
					const error = new Error(data.detail || '请求失败');
					error.statusCode = statusCode;
					error.data = data;
					reject(error);
				}
			},
			fail: (err) => {
				reject(new Error("服务器请求失败！"));
			}
		})
	})
}

const get = (url, data) => {
	let options = {data, method: 'GET'};
	return request(url, options);
}

const post = (url, data) => {
	let options = {data, method: "POST"};
	return request(url, options);
}

const put = (url, data) => {
	let options = {data, method: "PUT"};
	return request(url, options);
}

const login = (email, password) => {
	let url = "/user/login";
	return post(url, {email, password});
}

const register = (data) => {
	let url = "/user/register";
	return post(url, data);
}
const getEmailCode = (email) => {
	let url = "/user/code"
	return get(url, {email});
}
const resetPassword = (data) => {
	let url = "/user/reset"
	return put(url, data);
}

const chat = (data) => {
	let url = "/agent/chat"
	return post(url, data);
}

export default {
	request,
	get,
	post,
	login,
	register,
	getEmailCode,
	resetPassword,
	chat
}
export { BASE_URL }