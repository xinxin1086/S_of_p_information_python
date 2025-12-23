/**
 * 前端API调用示例 (2024-12-22更新)
 * 使用 /api/public/* 专用公开接口 + 完整的认证接口示例
 *
 * 适用于任何前端框架（React、Vue、原生JS等）
 */

// API基础配置
const API_BASE_URL = 'http://localhost:5000'; // 后端服务地址
const SCIENCE_API_BASE = '/api/public/science';
const ACTIVITIES_API_BASE = '/api/public/activities';
const USER_API_BASE = '/api/user';
const ADMIN_API_BASE = '/api/admin';
const FORUM_API_BASE = '/api/forum';
const COMMON_API_BASE = '/api/common';

// 响应数据类型定义
/**
 * @typedef {Object} APIResponse
 * @property {boolean} success - 请求是否成功
 * @property {string} message - 响应消息
 * @property {any} data - 响应数据
 */

/**
 * @typedef {Object} Article
 * @property {number} id - 文章ID
 * @property {string} title - 标题
 * @property {string} content - 内容
 * @property {string} cover_image - 封面图片
 * @property {number} like_count - 点赞数
 * @property {number} view_count - 浏览数
 * @property {string} author_account - 作者账号
 * @property {string} author_display - 作者显示名
 * @property {Object} author_info - 作者详细信息
 * @property {string} published_at - 发布时间
 * @property {string} created_at - 创建时间
 */

/**
 * @typedef {Object} PaginatedResponse
 * @property {Article[]} items - 文章列表
 * @property {number} total - 总数
 * @property {number} page - 当前页
 * @property {number} size - 页大小
 */

/**
 * @typedef {Object} Statistics
 * @property {number} total_published - 已发布文章数
 * @property {number} total_likes - 总点赞数
 * @property {number} total_views - 总浏览数
 * @property {number} avg_likes - 平均点赞数
 * @property {number} avg_views - 平均浏览数
 * @property {number} recent_published_30days - 最近30天发布数
 */

// 科普文章API服务类
class ScienceArticleService {
    /**
     * 获取科普文章列表
     * @param {Object} params - 查询参数
     * @param {number} params.page - 页码，默认1
     * @param {number} params.size - 每页数量，默认10
     * @param {string} params.keyword - 关键词搜索
     * @param {string} params.author_account - 作者账号筛选
     * @returns {Promise<APIResponse<PaginatedResponse>>}
     */
    static async getArticles(params = {}) {
        const {
            page = 1,
            size = 10,
            keyword = '',
            author_account = ''
        } = params;

        // 构建查询参数
        const queryParams = new URLSearchParams({
            page: page.toString(),
            size: size.toString()
        });

        if (keyword.trim()) {
            queryParams.append('keyword', keyword.trim());
        }
        if (author_account.trim()) {
            queryParams.append('author_account', author_account.trim());
        }

        try {
            const response = await fetch(`${SCIENCE_API_BASE}/articles?${queryParams}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取文章列表失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 获取科普文章详情
     * @param {number} articleId - 文章ID
     * @returns {Promise<APIResponse<Article>>}
     */
    static async getArticleDetail(articleId) {
        if (!articleId || isNaN(articleId)) {
            return {
                success: false,
                message: '文章ID无效',
                data: null
            };
        }

        try {
            const response = await fetch(`${SCIENCE_API_BASE}/articles/${articleId}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取文章详情失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 获取科普文章统计信息
     * @returns {Promise<APIResponse<Statistics>>}
     */
    static async getStatistics() {
        try {
            const response = await fetch(`${SCIENCE_API_BASE}/articles/statistics`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取统计信息失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 格式化时间
     * @param {string} isoString - ISO时间字符串
     * @returns {string} 格式化后的时间
     */
    static formatDate(isoString) {
        if (!isoString) return '未知时间';

        try {
            const date = new Date(isoString);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return isoString;
        }
    }

    /**
     * 截取文章摘要
     * @param {string} content - 文章内容
     * @param {number} length - 摘要长度，默认100
     * @returns {string} 摘要
     */
    static extractSummary(content, length = 100) {
        if (!content) return '';

        // 移除HTML标签
        const textContent = content.replace(/<[^>]*>/g, '');

        if (textContent.length <= length) {
            return textContent;
        }

        return textContent.substring(0, length) + '...';
    }
}

// 使用示例
async function exampleUsage() {
    console.log('=== 科普文章API使用示例 ===');

    // 1. 获取文章列表
    console.log('\n1. 获取文章列表:');
    const articlesResult = await ScienceArticleService.getArticles({
        page: 1,
        size: 5
    });

    if (articlesResult.success) {
        console.log(`获取到 ${articlesResult.data.total} 篇文章`);
        console.log('第一篇文章:', articlesResult.data.items[0]);
    } else {
        console.error('获取文章列表失败:', articlesResult.message);
    }

    // 2. 关键词搜索
    console.log('\n2. 关键词搜索:');
    const searchResult = await ScienceArticleService.getArticles({
        page: 1,
        size: 3,
        keyword: '科学'
    });

    if (searchResult.success) {
        console.log(`搜索到 ${searchResult.data.total} 篇相关文章`);
    }

    // 3. 获取文章详情
    console.log('\n3. 获取文章详情:');
    if (articlesResult.success && articlesResult.data.items.length > 0) {
        const articleId = articlesResult.data.items[0].id;
        const detailResult = await ScienceArticleService.getArticleDetail(articleId);

        if (detailResult.success) {
            console.log('文章标题:', detailResult.data.title);
            console.log('作者:', detailResult.data.author_display);
            console.log('发布时间:', ScienceArticleService.formatDate(detailResult.data.published_at));
        }
    }

    // 4. 获取统计信息
    console.log('\n4. 获取统计信息:');
    const statsResult = await ScienceArticleService.getStatistics();

    if (statsResult.success) {
        console.log('总文章数:', statsResult.data.total_published);
        console.log('总点赞数:', statsResult.data.total_likes);
        console.log('总浏览数:', statsResult.data.total_views);
    }
}

// React Hook 示例
function useScienceArticles() {
    const [articles, setArticles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [pagination, setPagination] = useState({ total: 0, page: 1, size: 10 });

    const fetchArticles = async (params = {}) => {
        setLoading(true);
        setError(null);

        try {
            const result = await ScienceArticleService.getArticles(params);

            if (result.success) {
                setArticles(result.data.items);
                setPagination({
                    total: result.data.total,
                    page: result.data.page,
                    size: result.data.size
                });
            } else {
                setError(result.message);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return {
        articles,
        loading,
        error,
        pagination,
        fetchArticles
    };
}

// Vue Composable 示例
function useScienceArticles() {
    const articles = ref([]);
    const loading = ref(false);
    const error = ref(null);
    const pagination = ref({ total: 0, page: 1, size: 10 });

    const fetchArticles = async (params = {}) => {
        loading.value = true;
        error.value = null;

        try {
            const result = await ScienceArticleService.getArticles(params);

            if (result.success) {
                articles.value = result.data.items;
                pagination.value = {
                    total: result.data.total,
                    page: result.data.page,
                    size: result.data.size
                };
            } else {
                error.value = result.message;
            }
        } catch (err) {
            error.value = err.message;
        } finally {
            loading.value = false;
        }
    };

    return {
        articles: readonly(articles),
        loading: readonly(loading),
        error: readonly(error),
        pagination: readonly(pagination),
        fetchArticles
    };
}

// ========== 活动API服务类 ==========

/**
 * @typedef {Object} Activity
 * @property {number} id - 活动ID
 * @property {string} title - 标题
 * @property {string} description - 描述
 * @property {string} location - 活动地点
 * @property {string} start_time - 开始时间
 * @property {string} end_time - 结束时间
 * @property {number} max_participants - 最大参与人数
 * @property {number} current_participants - 当前参与人数
 * @property {string} organizer_display - 组织者显示名
 * @property {string} activity_status - 活动状态
 * @property {string} status_info - 状态信息
 * @property {boolean} can_book - 是否可以报名
 * @property {string} status - 活动状态
 */

/**
 * @typedef {Object} ActivityStatistics
 * @property {number} total_published - 已发布活动数
 * @property {number} upcoming_count - 即将开始的活动数
 * @property {number} ongoing_count - 进行中的活动数
 * @property {number} completed_count - 已结束的活动数
 * @property {number} recent_published_30days - 最近30天发布数
 * @property {number} total_bookings - 总预约数
 * @property {number} unique_participants - 参与用户数
 */

// 活动API服务类
class ActivityService {
    /**
     * 获取活动列表
     * @param {Object} params - 查询参数
     * @param {number} params.page - 页码，默认1
     * @param {number} params.size - 每页数量，默认10
     * @param {string} params.keyword - 关键词搜索
     * @param {string} params.organizer_display - 组织者筛选
     * @param {string} params.status - 活动状态筛选
     * @param {string} params.start_date - 开始时间筛选
     * @param {string} params.end_date - 结束时间筛选
     * @returns {Promise<APIResponse>}
     */
    static async getActivities(params = {}) {
        const {
            page = 1,
            size = 10,
            keyword = '',
            organizer_display = '',
            status = 'published',
            start_date = '',
            end_date = ''
        } = params;

        // 构建查询参数
        const queryParams = new URLSearchParams({
            page: page.toString(),
            size: size.toString(),
            status: status
        });

        if (keyword.trim()) {
            queryParams.append('keyword', keyword.trim());
        }
        if (organizer_display.trim()) {
            queryParams.append('organizer_display', organizer_display.trim());
        }
        if (start_date.trim()) {
            queryParams.append('start_date', start_date.trim());
        }
        if (end_date.trim()) {
            queryParams.append('end_date', end_date.trim());
        }

        try {
            const response = await fetch(`${ACTIVITIES_API_BASE}/activities?${queryParams}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取活动列表失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 获取活动详情
     * @param {number} activityId - 活动ID
     * @returns {Promise<APIResponse<Activity>>}
     */
    static async getActivityDetail(activityId) {
        if (!activityId || isNaN(activityId)) {
            return {
                success: false,
                message: '活动ID无效',
                data: null
            };
        }

        try {
            const response = await fetch(`${ACTIVITIES_API_BASE}/activities/${activityId}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取活动详情失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 获取活动统计信息
     * @returns {Promise<APIResponse<ActivityStatistics>>}
     */
    static async getStatistics() {
        try {
            const response = await fetch(`${ACTIVITIES_API_BASE}/activities/statistics`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取活动统计失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 格式化时间
     * @param {string} isoString - ISO时间字符串
     * @returns {string} 格式化后的时间
     */
    static formatDate(isoString) {
        if (!isoString) return '未知时间';

        try {
            const date = new Date(isoString);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return isoString;
        }
    }

    /**
     * 截取活动描述摘要
     * @param {string} description - 活动描述
     * @param {number} length - 摘要长度，默认150
     * @returns {string} 摘要
     */
    static extractSummary(description, length = 150) {
        if (!description) return '';

        // 移除HTML标签
        const textContent = description.replace(/<[^>]*>/g, '');

        if (textContent.length <= length) {
            return textContent;
        }

        return textContent.substring(0, length) + '...';
    }
}

// 使用示例更新
async function exampleUsage() {
    console.log('=== 前端API使用示例 (更新版) ===');

    // 1. 获取科普文章列表
    console.log('\n1. 获取科普文章列表:');
    const articlesResult = await ScienceArticleService.getArticles({
        page: 1,
        size: 5
    });

    if (articlesResult.success) {
        console.log(`获取到 ${articlesResult.data.total} 篇文章`);
    } else {
        console.error('获取文章列表失败:', articlesResult.message);
    }

    // 2. 获取活动列表
    console.log('\n2. 获取活动列表:');
    const activitiesResult = await ActivityService.getActivities({
        page: 1,
        size: 5,
        keyword: '技术'
    });

    if (activitiesResult.success) {
        console.log(`获取到 ${activitiesResult.data.total} 个活动`);
    } else {
        console.error('获取活动列表失败:', activitiesResult.message);
    }

    // 3. 获取统计信息
    console.log('\n3. 获取统计信息:');
    const scienceStats = await ScienceArticleService.getStatistics();
    const activityStats = await ActivityService.getStatistics();

    if (scienceStats.success && activityStats.success) {
        console.log('科普文章统计:', scienceStats.data);
        console.log('活动统计:', activityStats.data);
    }
}

// 导出服务类
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ScienceArticleService, ActivityService };
}

// 如果在浏览器环境中，全局可用
if (typeof window !== 'undefined') {
    window.ScienceArticleService = ScienceArticleService;
    window.ActivityService = ActivityService;
}

// ========== 用户认证服务类 ==========

/**
 * @typedef {Object} User
 * @property {number} id - 用户ID
 * @property {string} account - 账号
 * @property {string} username - 用户名
 * @property {string} email - 邮箱
 * @property {string} role - 角色
 * @property {string} avatar_url - 头像URL
 */

// 用户认证服务类
class AuthService {
    static token = null;
    static user = null;

    /**
     * 用户登录
     * @param {string} account - 用户账号
     * @param {string} password - 密码
     * @returns {Promise<APIResponse>}
     */
    static async login(account, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/user/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ account, password })
            });

            const data = await response.json();

            if (data.success) {
                this.token = data.data.token;
                this.user = data.data.user_info;
                // 存储到localStorage
                localStorage.setItem('token', this.token);
                localStorage.setItem('user', JSON.stringify(this.user));
            }

            return data;
        } catch (error) {
            console.error('登录失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 管理员登录
     * @param {string} account - 管理员账号
     * @param {string} password - 密码
     * @returns {Promise<APIResponse>}
     */
    static async adminLogin(account, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/admin/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ account, password })
            });

            const data = await response.json();

            if (data.success) {
                this.token = data.data.token;
                this.user = data.data.user;
                localStorage.setItem('token', this.token);
                localStorage.setItem('user', JSON.stringify(this.user));
            }

            return data;
        } catch (error) {
            console.error('管理员登录失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 用户注册
     * @param {Object} userData - 用户数据
     * @param {string} userData.account - 账号
     * @param {string} userData.password - 密码
     * @param {string} userData.username - 用户名
     * @param {string} userData.email - 邮箱
     * @param {string} userData.phone - 手机号
     * @returns {Promise<APIResponse>}
     */
    static async register(userData) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/user/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });

            return await response.json();
        } catch (error) {
            console.error('注册失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 获取当前用户信息
     * @returns {Promise<APIResponse>}
     */
    static async getUserInfo() {
        try {
            const response = await this.authenticatedFetch(`${API_BASE_URL}/api/user/info`);
            const data = await response.json();

            if (data.success) {
                this.user = data.data;
                localStorage.setItem('user', JSON.stringify(this.user));
            }

            return data;
        } catch (error) {
            console.error('获取用户信息失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 更新用户信息
     * @param {Object} userData - 更新的用户数据
     * @returns {Promise<APIResponse>}
     */
    static async updateUserInfo(userData) {
        try {
            const response = await this.authenticatedFetch(`${API_BASE_URL}/api/user/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });

            return await response.json();
        } catch (error) {
            console.error('更新用户信息失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 登出
     */
    static logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    }

    /**
     * 获取认证头
     * @returns {Object}
     */
    static getAuthHeaders() {
        const token = this.token || localStorage.getItem('token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    /**
     * 发起需要认证的请求
     * @param {string} url - 请求URL
     * @param {Object} options - 请求选项
     * @returns {Promise<Response>}
     */
    static async authenticatedFetch(url, options = {}) {
        const headers = {
            ...this.getAuthHeaders(),
            ...options.headers
        };

        return fetch(url, {
            ...options,
            headers
        });
    }

    /**
     * 检查是否已登录
     * @returns {boolean}
     */
    static isLoggedIn() {
        return !!(this.token || localStorage.getItem('token'));
    }

    /**
     * 从localStorage恢复登录状态
     */
    static restoreFromStorage() {
        const token = localStorage.getItem('token');
        const user = localStorage.getItem('user');

        if (token) {
            this.token = token;
        }
        if (user) {
            try {
                this.user = JSON.parse(user);
            } catch (e) {
                console.error('解析用户信息失败:', e);
            }
        }
    }
}

// ========== 文件上传服务类 ==========

// 文件上传服务类
class FileUploadService {
    /**
     * 上传图片
     * @param {File} file - 图片文件
     * @returns {Promise<APIResponse>}
     */
    static async uploadImage(file) {
        if (!file) {
            return {
                success: false,
                message: '请选择文件',
                data: null
            };
        }

        // 检查文件类型
        if (!file.type.startsWith('image/')) {
            return {
                success: false,
                message: '只能上传图片文件',
                data: null
            };
        }

        // 检查文件大小 (5MB)
        if (file.size > 5 * 1024 * 1024) {
            return {
                success: false,
                message: '文件大小不能超过5MB',
                data: null
            };
        }

        try {
            const formData = new FormData();
            formData.append('image', file);

            const response = await AuthService.authenticatedFetch(`${API_BASE_URL}/api/common/upload/image`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('图片上传失败:', error);
            return {
                success: false,
                message: error.message || '上传失败',
                data: null
            };
        }
    }

    /**
     * 上传头像
     * @param {File} file - 头像文件
     * @returns {Promise<APIResponse>}
     */
    static async uploadAvatar(file) {
        if (!file) {
            return {
                success: false,
                message: '请选择文件',
                data: null
            };
        }

        // 检查文件类型和大小
        if (!file.type.startsWith('image/')) {
            return {
                success: false,
                message: '只能上传图片文件',
                data: null
            };
        }

        if (file.size > 2 * 1024 * 1024) {
            return {
                success: false,
                message: '头像文件大小不能超过2MB',
                data: null
            };
        }

        try {
            const formData = new FormData();
            formData.append('avatar', file);

            const response = await AuthService.authenticatedFetch(`${API_BASE_URL}/api/common/upload/avatar`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('头像上传失败:', error);
            return {
                success: false,
                message: error.message || '上传失败',
                data: null
            };
        }
    }

    /**
     * 删除图片
     * @param {string} imageUrl - 图片URL
     * @returns {Promise<APIResponse>}
     */
    static async deleteImage(imageUrl) {
        if (!imageUrl) {
            return {
                success: false,
                message: '图片URL不能为空',
                data: null
            };
        }

        try {
            const response = await AuthService.authenticatedFetch(`${API_BASE_URL}/api/common/delete/image`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ image_url: imageUrl })
            });

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('删除图片失败:', error);
            return {
                success: false,
                message: error.message || '删除失败',
                data: null
            };
        }
    }
}

// ========== 论坛服务类 ==========

/**
 * @typedef {Object} ForumPost
 * @property {number} id - 帖子ID
 * @property {string} title - 标题
 * @property {string} content - 内容
 * @property {string} author_account - 作者账号
 * @property {string} author_display - 作者显示名
 * @property {string} category - 分类
 * @property {number} like_count - 点赞数
 * @property {number} view_count - 浏览数
 * @property {string} created_at - 创建时间
 */

// 论坛服务类
class ForumService {
    /**
     * 获取帖子列表
     * @param {Object} params - 查询参数
     * @param {number} params.page - 页码，默认1
     * @param {number} params.size - 每页数量，默认10
     * @param {string} params.category - 分类筛选
     * @param {string} params.keyword - 关键词搜索
     * @returns {Promise<APIResponse>}
     */
    static async getPosts(params = {}) {
        const {
            page = 1,
            size = 10,
            category = '',
            keyword = ''
        } = params;

        const queryParams = new URLSearchParams({
            page: page.toString(),
            size: size.toString()
        });

        if (category.trim()) {
            queryParams.append('category', category.trim());
        }
        if (keyword.trim()) {
            queryParams.append('q', keyword.trim());
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/forum/posts?${queryParams}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取帖子列表失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 获取帖子详情
     * @param {number} postId - 帖子ID
     * @returns {Promise<APIResponse>}
     */
    static async getPostDetail(postId) {
        if (!postId || isNaN(postId)) {
            return {
                success: false,
                message: '帖子ID无效',
                data: null
            };
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/forum/posts/${postId}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP错误: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('获取帖子详情失败:', error);
            return {
                success: false,
                message: error.message || '网络请求失败',
                data: null
            };
        }
    }

    /**
     * 创建帖子
     * @param {Object} postData - 帖子数据
     * @param {string} postData.title - 标题
     * @param {string} postData.content - 内容
     * @param {string} postData.category - 分类
     * @param {string[]} postData.tags - 标签
     * @returns {Promise<APIResponse>}
     */
    static async createPost(postData) {
        if (!AuthService.isLoggedIn()) {
            return {
                success: false,
                message: '请先登录',
                data: null
            };
        }

        try {
            const response = await AuthService.authenticatedFetch(`${API_BASE_URL}/api/forum/posts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(postData)
            });

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('创建帖子失败:', error);
            return {
                success: false,
                message: error.message || '创建失败',
                data: null
            };
        }
    }

    /**
     * 点赞帖子
     * @param {number} postId - 帖子ID
     * @returns {Promise<APIResponse>}
     */
    static async likePost(postId) {
        if (!AuthService.isLoggedIn()) {
            return {
                success: false,
                message: '请先登录',
                data: null
            };
        }

        try {
            const response = await AuthService.authenticatedFetch(`${API_BASE_URL}/api/forum/posts/${postId}/like`, {
                method: 'POST'
            });

            const data = await response.json();
            return data;
        } catch (error) {
            console.error('点赞失败:', error);
            return {
                success: false,
                message: error.message || '操作失败',
                data: null
            };
        }
    }

    /**
     * 搜索帖子
     * @param {string} keyword - 搜索关键词
     * @param {Object} params - 其他查询参数
     * @returns {Promise<APIResponse>}
     */
    static async searchPosts(keyword, params = {}) {
        return this.getPosts({ ...params, keyword });
    }
}

// ========== 完整的使用示例更新 ==========

// 完整使用示例
async function completeExampleUsage() {
    console.log('=== 完整前端API使用示例 ===');

    // 1. 用户登录
    console.log('\n1. 用户登录:');
    const loginResult = await AuthService.login('user123', 'password123');
    if (loginResult.success) {
        console.log('登录成功:', loginResult.data.user_info);
    } else {
        console.error('登录失败:', loginResult.message);
        return; // 如果登录失败，后续操作无法进行
    }

    // 2. 获取用户信息
    console.log('\n2. 获取用户信息:');
    const userInfoResult = await AuthService.getUserInfo();
    if (userInfoResult.success) {
        console.log('用户信息:', userInfoResult.data);
    }

    // 3. 上传头像
    console.log('\n3. 上传头像:');
    // 假设有一个文件选择
    // const avatarFile = document.getElementById('avatar-input').files[0];
    // if (avatarFile) {
    //     const uploadResult = await FileUploadService.uploadAvatar(avatarFile);
    //     if (uploadResult.success) {
    //         console.log('头像上传成功:', uploadResult.data);
    //     }
    // }

    // 4. 获取科普文章列表
    console.log('\n4. 获取科普文章列表:');
    const articlesResult = await ScienceArticleService.getArticles({
        page: 1,
        size: 5,
        keyword: '科学'
    });

    if (articlesResult.success) {
        console.log(`获取到 ${articlesResult.data.total} 篇文章`);
    }

    // 5. 获取活动列表
    console.log('\n5. 获取活动列表:');
    const activitiesResult = await ActivityService.getActivities({
        page: 1,
        size: 5
    });

    if (activitiesResult.success) {
        console.log(`获取到 ${activitiesResult.data.total} 个活动`);
    }

    // 6. 获取论坛帖子列表
    console.log('\n6. 获取论坛帖子列表:');
    const postsResult = await ForumService.getPosts({
        page: 1,
        size: 5,
        category: 'discussion'
    });

    if (postsResult.success) {
        console.log(`获取到 ${postsResult.data.total} 个帖子`);
    }

    // 7. 创建论坛帖子
    console.log('\n7. 创建论坛帖子:');
    const createPostResult = await ForumService.createPost({
        title: '测试帖子标题',
        content: '这是测试帖子的内容...',
        category: 'discussion',
        tags: ['测试', '前端']
    });

    if (createPostResult.success) {
        console.log('帖子创建成功:', createPostResult.data);
    } else {
        console.error('创建帖子失败:', createPostResult.message);
    }

    // 8. 登出
    console.log('\n8. 用户登出:');
    AuthService.logout();
    console.log('已登出');
}

// ========== 初始化和工具函数 ==========

/**
 * 页面加载时恢复登录状态
 */
function initializeApp() {
    // 从localStorage恢复登录状态
    AuthService.restoreFromStorage();

    if (AuthService.isLoggedIn()) {
        console.log('用户已登录:', AuthService.user);
    }
}

// 自动运行示例（仅在直接运行时）
if (typeof window !== 'undefined' && window.location.pathname.includes('example')) {
    // 等待页面加载完成后运行示例
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initializeApp();
            completeExampleUsage();
        });
    } else {
        initializeApp();
        completeExampleUsage();
    }
}