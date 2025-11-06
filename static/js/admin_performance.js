/**
 * Admin Performance Manager
 * Handles lazy loading, caching, and performance optimizations for admin interface
 */

class AdminPerformanceManager {
    constructor(config = {}) {
        this.config = {
            endpoint: config.endpoint || window.location.pathname,
            pageSize: config.pageSize || 50,
            enableLazyLoad: config.enableLazyLoad !== false,
            enableVirtualScroll: config.enableVirtualScroll || false,
            enableCaching: config.enableCaching !== false,
            cacheTimeout: config.cacheTimeout || 300000, // 5 minutes
            ...config
        };
        
        this.state = {
            currentPage: 1,
            totalPages: 1,
            totalCount: 0,
            isLoading: false,
            hasMoreData: true,
            cache: new Map(),
            lastRequestTime: 0,
            searchQuery: '',
            sortColumn: null,
            sortDesc: false
        };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadInitialData();
    }
    
    setupEventListeners() {
        // Performance toggle controls
        const lazyLoadToggle = document.getElementById('toggleLazyLoad');
        if (lazyLoadToggle) {
            lazyLoadToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleLazyLoad();
            });
        }
        
        const virtualScrollToggle = document.getElementById('toggleVirtualScroll');
        if (virtualScrollToggle) {
            virtualScrollToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleVirtualScroll();
            });
        }
        
        const refreshButton = document.getElementById('refreshData');
        if (refreshButton) {
            refreshButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.refreshData();
            });
        }
        
        // Search with debouncing
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.performSearch(e.target.value);
                }, 300);
            });
        }
        
        // Infinite scroll for lazy loading
        if (this.config.enableLazyLoad) {
            window.addEventListener('scroll', this.throttle(() => {
                this.checkScrollPosition();
            }, 100));
        }
    }
    
    async loadInitialData() {
        this.showLoading();
        this.showSkeletonLoader();
        
        try {
            const response = await this.fetchData(1, this.config.pageSize);
            this.renderData(response.data, response.pagination);
            this.updateRecordCount(response.pagination.total);
            this.hideLoading();
            this.hideSkeletonLoader();
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showError('Failed to load data. Please try again.');
            this.hideLoading();
            this.hideSkeletonLoader();
        }
    }
    
    async fetchData(page = 1, pageSize = null, search = '', sort = null, sortDesc = false) {
        const cacheKey = this.generateCacheKey(page, pageSize || this.config.pageSize, search, sort, sortDesc);
        
        // Check cache first
        if (this.config.enableCaching && this.state.cache.has(cacheKey)) {
            const cached = this.state.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.config.cacheTimeout) {
                return cached.data;
            }
        }
        
        // Build query parameters
        const params = new URLSearchParams({
            page: page.toString(),
            per_page: (pageSize || this.config.pageSize).toString()
        });
        
        if (search) {
            params.append('search', search);
        }
        
        if (sort) {
            params.append('sort', sort);
            if (sortDesc) {
                params.append('sort_desc', '1');
            }
        }
        
        const url = `${this.config.endpoint}?${params.toString()}`;
        
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Cache the response
            if (this.config.enableCaching) {
                this.state.cache.set(cacheKey, {
                    data: data,
                    timestamp: Date.now()
                });
                
                // Clean old cache entries
                this.cleanCache();
            }
            
            return data;
        } catch (error) {
            console.error('Fetch error:', error);
            throw error;
        }
    }
    
    async loadMoreData() {
        if (this.state.isLoading || !this.state.hasMoreData || !this.config.enableLazyLoad) {
            return;
        }
        
        this.state.isLoading = true;
        this.showLazyLoadingIndicator();
        
        try {
            const nextPage = this.state.currentPage + 1;
            const response = await this.fetchData(
                nextPage, 
                this.config.pageSize, 
                this.state.searchQuery,
                this.state.sortColumn,
                this.state.sortDesc
            );
            
            if (response.data && response.data.length > 0) {
                this.appendData(response.data);
                this.state.currentPage = nextPage;
                this.state.hasMoreData = response.pagination.has_next;
            } else {
                this.state.hasMoreData = false;
            }
            
            this.hideLazyLoadingIndicator();
        } catch (error) {
            console.error('Error loading more data:', error);
            this.showError('Failed to load more data.');
            this.hideLazyLoadingIndicator();
        } finally {
            this.state.isLoading = false;
        }
    }
    
    renderData(data, pagination) {
        const tableBody = document.getElementById('tableBody');
        const dataTable = document.getElementById('dataTable');
        const noDataMessage = document.getElementById('noDataMessage');
        
        if (!tableBody) return;
        
        if (data && data.length > 0) {
            tableBody.innerHTML = '';
            
            data.forEach(row => {
                const tr = this.createTableRow(row);
                tableBody.appendChild(tr);
            });
            
            if (dataTable) dataTable.style.display = 'block';
            if (noDataMessage) noDataMessage.style.display = 'none';
            
            this.updatePagination(pagination);
        } else {
            if (dataTable) dataTable.style.display = 'none';
            if (noDataMessage) noDataMessage.style.display = 'block';
        }
    }
    
    appendData(data) {
        const tableBody = document.getElementById('tableBody');
        if (!tableBody) return;
        
        data.forEach(row => {
            const tr = this.createTableRow(row);
            tableBody.appendChild(tr);
        });
    }
    
    createTableRow(row) {
        const tr = document.createElement('tr');
        
        // Add checkbox if actions are enabled
        const actionsEnabled = document.querySelector('.list-checkbox-column');
        if (actionsEnabled) {
            const checkboxTd = document.createElement('td');
            checkboxTd.innerHTML = `<input type="checkbox" name="rowid" class="action-checkbox" value="${row.id || ''}" />`;
            tr.appendChild(checkboxTd);
        }
        
        // Add data columns (this would need to be customized based on your model)
        Object.keys(row).forEach(key => {
            if (key !== 'id' && typeof row[key] !== 'object') {
                const td = document.createElement('td');
                td.textContent = row[key] || '';
                tr.appendChild(td);
            }
        });
        
        // Add actions column
        const actionsColumn = document.querySelector('.list-actions-column');
        if (actionsColumn) {
            const actionsTd = document.createElement('td');
            actionsTd.className = 'list-actions-column';
            actionsTd.innerHTML = `
                <a class="btn btn-sm btn-primary btn-icon" href="/admin/pollingplace/edit/${row.id}" title="Edit record">
                    <i class="fa fa-edit"></i>
                </a>
                <form class="inline-form" method="POST" action="/admin/pollingplace/delete/${row.id}">
                    <button class="btn btn-sm btn-danger btn-icon" onclick="return confirm('Are you sure you want to delete this record?');" title="Delete record">
                        <i class="fa fa-trash"></i>
                    </button>
                </form>
            `;
            tr.appendChild(actionsTd);
        }
        
        return tr;
    }
    
    updatePagination(pagination) {
        if (!pagination) return;
        
        this.state.currentPage = pagination.page;
        this.state.totalPages = pagination.total_pages;
        this.state.totalCount = pagination.total;
        
        this.updatePaginationInfo();
        this.updatePaginationControls();
    }
    
    updatePaginationInfo() {
        const infoElement = document.getElementById('paginationInfo');
        if (!infoElement) return;
        
        const start = (this.state.currentPage - 1) * this.config.pageSize + 1;
        const end = Math.min(this.state.currentPage * this.config.pageSize, this.state.totalCount);
        
        infoElement.textContent = `Showing ${start} to ${end} of ${this.state.totalCount} records`;
    }
    
    updatePaginationControls() {
        const controlsElement = document.getElementById('paginationControls');
        if (!controlsElement) return;
        
        controlsElement.innerHTML = '';
        
        // Previous button
        if (this.state.currentPage > 1) {
            const prevBtn = this.createPaginationButton('Previous', this.state.currentPage - 1);
            controlsElement.appendChild(prevBtn);
        }
        
        // Page numbers
        const startPage = Math.max(1, this.state.currentPage - 2);
        const endPage = Math.min(this.state.totalPages, this.state.currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = this.createPaginationButton(i.toString(), i, i === this.state.currentPage);
            controlsElement.appendChild(pageBtn);
        }
        
        // Next button
        if (this.state.currentPage < this.state.totalPages) {
            const nextBtn = this.createPaginationButton('Next', this.state.currentPage + 1);
            controlsElement.appendChild(nextBtn);
        }
    }
    
    createPaginationButton(text, page, isActive = false) {
        const button = document.createElement('button');
        button.className = `btn ${isActive ? 'btn-primary' : 'btn-secondary'}`;
        button.textContent = text;
        button.addEventListener('click', () => this.goToPage(page));
        return button;
    }
    
    async goToPage(page) {
        if (page === this.state.currentPage || this.state.isLoading) {
            return;
        }
        
        this.showLoading();
        
        try {
            const response = await this.fetchData(
                page, 
                this.config.pageSize, 
                this.state.searchQuery,
                this.state.sortColumn,
                this.state.sortDesc
            );
            this.renderData(response.data, response.pagination);
        } catch (error) {
            console.error('Error navigating to page:', error);
            this.showError('Failed to load page.');
        } finally {
            this.hideLoading();
        }
    }
    
    async performSearch(query) {
        this.state.searchQuery = query;
        this.state.currentPage = 1;
        
        this.showLoading();
        
        try {
            const response = await this.fetchData(
                1, 
                this.config.pageSize, 
                query,
                this.state.sortColumn,
                this.state.sortDesc
            );
            this.renderData(response.data, response.pagination);
        } catch (error) {
            console.error('Error performing search:', error);
            this.showError('Search failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }
    
    async refreshData() {
        // Clear cache
        this.state.cache.clear();
        
        // Reload current page
        await this.goToPage(this.state.currentPage);
    }
    
    toggleLazyLoad() {
        this.config.enableLazyLoad = !this.config.enableLazyLoad;
        const toggle = document.getElementById('toggleLazyLoad');
        if (toggle) {
            const icon = toggle.querySelector('i');
            if (this.config.enableLazyLoad) {
                icon.className = 'fa fa-check';
            } else {
                icon.className = 'fa fa-times';
            }
        }
    }
    
    toggleVirtualScroll() {
        this.config.enableVirtualScroll = !this.config.enableVirtualScroll;
        const toggle = document.getElementById('toggleVirtualScroll');
        if (toggle) {
            const icon = toggle.querySelector('i');
            if (this.config.enableVirtualScroll) {
                icon.className = 'fa fa-check';
            } else {
                icon.className = 'fa fa-times';
            }
        }
    }
    
    checkScrollPosition() {
        if (!this.config.enableLazyLoad) return;
        
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const windowHeight = window.innerHeight;
        const documentHeight = document.documentElement.scrollHeight;
        
        if (scrollTop + windowHeight >= documentHeight - 100) {
            this.loadMoreData();
        }
    }
    
    generateCacheKey(page, pageSize, search, sort, sortDesc) {
        return `${page}_${pageSize}_${search}_${sort}_${sortDesc}`;
    }
    
    cleanCache() {
        const now = Date.now();
        for (const [key, value] of this.state.cache.entries()) {
            if (now - value.timestamp > this.config.cacheTimeout) {
                this.state.cache.delete(key);
            }
        }
    }
    
    updateRecordCount(count) {
        const countElement = document.getElementById('recordCount');
        if (countElement) {
            countElement.textContent = `${count} total records`;
        }
    }
    
    showLoading() {
        this.state.isLoading = true;
        // Update UI to show loading state
    }
    
    hideLoading() {
        this.state.isLoading = false;
        // Update UI to hide loading state
    }
    
    showSkeletonLoader() {
        const skeleton = document.getElementById('skeletonLoader');
        if (skeleton) {
            skeleton.style.display = 'block';
        }
    }
    
    hideSkeletonLoader() {
        const skeleton = document.getElementById('skeletonLoader');
        if (skeleton) {
            skeleton.style.display = 'none';
        }
    }
    
    showLazyLoadingIndicator() {
        const indicator = document.getElementById('lazyLoadingIndicator');
        if (indicator) {
            indicator.style.display = 'block';
        }
    }
    
    hideLazyLoadingIndicator() {
        const indicator = document.getElementById('lazyLoadingIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }
    
    showError(message) {
        // Simple error display - could be enhanced with a toast notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = message;
        
        const container = document.querySelector('.panel-body');
        if (container) {
            container.insertBefore(errorDiv, container.firstChild);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.parentNode.removeChild(errorDiv);
                }
            }, 5000);
        }
    }
    
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdminPerformanceManager;
}