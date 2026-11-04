/**
 * Nexis Cyber Recovery - High Performance Animation & Experience Engine
 * Lightweight, zero-dependency, 60fps/120fps hardware-accelerated animations.
 */

(function () {
    'use strict';

    // Respect user's motion preferences
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    document.addEventListener('DOMContentLoaded', function () {
        initReadingProgressBar();
        initNavbarElevation();
        initAutoRevealTags();
        initScrollObserver();
        initStatCounters();
        initButtonRipples();
        initSlideOutAlerts();
        initModalAnimations();
        initCollapseAnimations();
        initLazyImages();
    });

    /**
     * 1. Top Reading Scroll Progress Indicator
     */
    function initReadingProgressBar() {
        const progressBar = document.getElementById('reading-progress');
        if (!progressBar) return;

        let ticking = false;
        window.addEventListener('scroll', function () {
            if (!ticking) {
                window.requestAnimationFrame(function () {
                    const winScroll = document.documentElement.scrollTop || document.body.scrollTop;
                    const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
                    const scrolled = height > 0 ? (winScroll / height) * 100 : 0;
                    progressBar.style.width = scrolled + '%';
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
    }

    /**
     * 2. Navbar Elevation & Glass Effect on Scroll
     */
    function initNavbarElevation() {
        const navbar = document.querySelector('.navbar');
        if (!navbar) return;

        let ticking = false;
        function updateNav() {
            if (window.scrollY > 20) {
                navbar.classList.add('shadow');
                navbar.style.backgroundColor = 'rgba(10, 25, 47, 0.96)';
                navbar.style.backdropFilter = 'blur(10px)';
                navbar.style.webkitBackdropFilter = 'blur(10px)';
            } else {
                navbar.classList.remove('shadow');
                navbar.style.backgroundColor = '';
                navbar.style.backdropFilter = '';
                navbar.style.webkitBackdropFilter = '';
            }
            ticking = false;
        }

        window.addEventListener('scroll', function () {
            if (!ticking) {
                window.requestAnimationFrame(updateNav);
                ticking = true;
            }
        }, { passive: true });
        updateNav();
    }

    /**
     * 3. Automatic Animation Tagging for All Pages and Contents
     * Automatically applies directional slide reveals to content elements
     * across all marketing, legal, portal, and account dashboard pages.
     */
    function initAutoRevealTags() {
        if (prefersReducedMotion) return;

        // Auto tag cards and containers that don't yet have reveal classes
        const targets = [
            { selector: '.section-padding h2, .section-padding .lead, .hero-section h1, .hero-section .lead', class: 'reveal-up' },
            { selector: '.card:not(.reveal), .kpi-card:not(.reveal), .claim-card:not(.reveal)', class: 'reveal-up' },
            { selector: '.feature-icon', class: 'reveal-scale' },
            { selector: '.accordion-item', class: 'reveal-up' },
            { selector: '.timeline-horizontal .timeline-item', class: 'reveal-up' },
            { selector: '.table-responsive', class: 'reveal-up' }
        ];

        targets.forEach(function (target) {
            document.querySelectorAll(target.selector).forEach(function (el, index) {
                if (!el.classList.contains('reveal')) {
                    el.classList.add('reveal', target.class);
                    // Add staggered delays for siblings
                    const delayMod = (index % 5) * 100;
                    if (delayMod > 0) {
                        el.classList.add('delay-' + delayMod);
                    }
                }
            });
        });
    }

    /**
     * 4. Scroll & Viewport Observer for Smooth Slide-In Entrance
     * Instantly reveals above-the-fold content on page load and slides in
     * subsequent elements as user scrolls down.
     */
    function initScrollObserver() {
        const revealElements = document.querySelectorAll('.reveal');
        if (!revealElements.length) return;

        function revealElement(el) {
            el.classList.add('is-visible');
        }

        if (prefersReducedMotion || !('IntersectionObserver' in window)) {
            revealElements.forEach(revealElement);
            return;
        }

        // Immediately check elements already visible in viewport on page load
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        revealElements.forEach(function (el) {
            const rect = el.getBoundingClientRect();
            if (rect.top <= viewportHeight * 0.95 && rect.bottom >= 0) {
                revealElement(el);
            }
        });

        const observerOptions = {
            root: null,
            rootMargin: '0px 0px 50px 0px',
            threshold: 0.05
        };

        const observer = new IntersectionObserver(function (entries, obs) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    revealElement(entry.target);
                    // Unobserve to free GPU compositing memory
                    obs.unobserve(entry.target);
                }
            });
        }, observerOptions);

        revealElements.forEach(function (el) {
            if (!el.classList.contains('is-visible')) {
                observer.observe(el);
            }
        });
    }

    /**
     * 5. Animated Number Counter for Impact Statistics
     */
    function initStatCounters() {
        const statElements = document.querySelectorAll('h2.text-navy, .display-4, .stat-value');
        if (!statElements.length || prefersReducedMotion) return;

        const statObserver = new IntersectionObserver(function (entries, observer) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const text = el.textContent.trim();
                    
                    // Match numeric part with optional prefix/suffix: e.g. "$50M+", "98.5%", "12,000+"
                    const match = text.match(/^([^0-9]*)([0-9,.]+)(.*)$/);
                    if (match && !el.dataset.animated) {
                        el.dataset.animated = 'true';
                        const prefix = match[1];
                        const numStr = match[2].replace(/,/g, '');
                        const suffix = match[3];
                        const targetValue = parseFloat(numStr);

                        if (!isNaN(targetValue) && targetValue > 0) {
                            const isDecimal = numStr.includes('.');
                            const duration = 1400; // ms
                            const startTime = performance.now();

                            function step(now) {
                                const elapsed = now - startTime;
                                const progress = Math.min(elapsed / duration, 1);
                                // Ease-out quint
                                const ease = 1 - Math.pow(1 - progress, 5);
                                const current = targetValue * ease;

                                const formatted = isDecimal ? current.toFixed(1) : Math.floor(current).toLocaleString();
                                el.textContent = prefix + formatted + suffix;

                                if (progress < 1) {
                                    requestAnimationFrame(step);
                                } else {
                                    el.textContent = text; // Ensure exact final display
                                }
                            }
                            requestAnimationFrame(step);
                        }
                    }
                    observer.unobserve(el);
                }
            });
        }, { threshold: 0.25 });

        statElements.forEach(function (el) {
            statObserver.observe(el);
        });
    }

    /**
     * 6. Tactile Button Micro-Ripple & Hover Feedback
     */
    function initButtonRipples() {
        const buttons = document.querySelectorAll('.btn-gold, .btn-navy, .btn-outline-light');
        buttons.forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                const rect = btn.getBoundingClientRect();
                const circle = document.createElement('span');
                const diameter = Math.max(rect.width, rect.height);
                const radius = diameter / 2;

                circle.style.width = circle.style.height = `${diameter}px`;
                circle.style.left = `${e.clientX - rect.left - radius}px`;
                circle.style.top = `${e.clientY - rect.top - radius}px`;
                circle.style.position = 'absolute';
                circle.style.borderRadius = '50%';
                circle.style.transform = 'scale(0)';
                circle.style.animation = 'rippleEffect 0.6s linear';
                circle.style.backgroundColor = 'rgba(255, 255, 255, 0.4)';
                circle.style.pointerEvents = 'none';

                const rippleStyle = document.getElementById('btn-ripple-style');
                if (!rippleStyle) {
                    const style = document.createElement('style');
                    style.id = 'btn-ripple-style';
                    style.textContent = `
                        @keyframes rippleEffect {
                            to {
                                transform: scale(3.5);
                                opacity: 0;
                            }
                        }
                    `;
                    document.head.appendChild(style);
                }

                const existing = btn.querySelector('.btn-ripple');
                if (existing) existing.remove();

                circle.classList.add('btn-ripple');
                btn.appendChild(circle);

                setTimeout(function () {
                    circle.remove();
                }, 600);
            });
        });
    }

    /**
     * 7. Slide-Out Animation for Dismissible Alerts & Flash Messages
     */
    function initSlideOutAlerts() {
        document.querySelectorAll('.alert').forEach(function (alert) {
            const closeBtn = alert.querySelector('.btn-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    alert.classList.add('slide-out-right');
                    setTimeout(function () {
                        if (window.bootstrap && bootstrap.Alert) {
                            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                            if (bsAlert) bsAlert.close();
                            else alert.remove();
                        } else {
                            alert.remove();
                        }
                    }, 400);
                });
            }
        });
    }

    /**
     * 8. Modal Slide-In and Slide-Out Animations
     */
    function initModalAnimations() {
        document.querySelectorAll('.modal').forEach(function (modal) {
            modal.addEventListener('show.bs.modal', function () {
                const dialog = modal.querySelector('.modal-dialog');
                if (dialog) {
                    dialog.classList.remove('slide-out-up');
                    dialog.classList.add('slide-in-down');
                }
            });
            modal.addEventListener('hide.bs.modal', function (e) {
                const dialog = modal.querySelector('.modal-dialog');
                if (dialog && !dialog.classList.contains('slide-out-up')) {
                    e.preventDefault();
                    dialog.classList.remove('slide-in-down');
                    dialog.classList.add('slide-out-up');
                    setTimeout(function () {
                        if (window.bootstrap && bootstrap.Modal) {
                            const inst = bootstrap.Modal.getInstance(modal);
                            if (inst) inst.hide();
                        }
                    }, 350);
                }
            });
        });
    }

    /**
     * 9. Collapsible Nav & Menu Slide-In Animations
     */
    function initCollapseAnimations() {
        ['navbarNav', 'sidebarPortalNav'].forEach(function (id) {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('show.bs.collapse', function () {
                el.classList.add('slide-in-down');
            });
        });
    }

    /**
     * 10. Automatic Image Performance Optimization
     * Ensures all images have async decoding and lazy loading for speed.
     */
    function initLazyImages() {
        document.querySelectorAll('img').forEach(function (img) {
            if (!img.hasAttribute('loading') && !img.closest('.carousel-item.active')) {
                img.setAttribute('loading', 'lazy');
            }
            if (!img.hasAttribute('decoding')) {
                img.setAttribute('decoding', 'async');
            }
        });
    }
})();
