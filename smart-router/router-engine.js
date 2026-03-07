/**
 * Smart Router - Routing Engine  
 * Main orchestration layer for intelligent model routing
 */

const ComplexityScorer = require('./complexity-scorer');
const ModelCapabilities = require('./model-capabilities');
const fs = require('fs');
const path = require('path');

class RouterEngine {
    constructor(config = {}) {
        this.scorer = new ComplexityScorer();
        this.capabilities = new ModelCapabilities();
        
        this.config = {
            // Default thresholds (can be overridden)
            simpleThreshold: 30,
            mediumThreshold: 70,
            
            // Routing targets
            models: {
                simple: 'ollama/gemma2:2b',
                medium: 'nvidia-nim/moonshotai/kimi-k2.5', 
                high: 'anthropic/claude-sonnet-4-20250514',
                fallback: 'anthropic/claude-opus-4-20250514'
            },
            
            // Feature flags
            enableRouting: true,
            enableLogging: true,
            enableStats: true,
            
            ...config
        };
        
        // Stats tracking
        this.stats = {
            totalRequests: 0,
            routingDecisions: {
                simple: 0,
                medium: 0, 
                high: 0,
                fallback: 0
            },
            averageComplexity: 0,
            costSavings: 0 // Estimated savings vs always using premium
        };
        
        // Load timeout configuration after config is set
        this.loadTimeoutConfig();
        
        this.log('Smart Router initialized', this.config);
    }
    
    /**
     * Load timeout configuration
     */
    loadTimeoutConfig() {
        try {
            const configPath = path.join(__dirname, 'timeout-config.json');
            if (fs.existsSync(configPath)) {
                const timeoutConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
                this.timeoutConfig = timeoutConfig;
                this.log('Timeout configuration loaded');
            } else {
                this.timeoutConfig = { timeouts: { models: {} }, global: { enableTimeouts: false } };
            }
        } catch (error) {
            this.log('Error loading timeout config:', error);
            this.timeoutConfig = { timeouts: { models: {} }, global: { enableTimeouts: false } };
        }
    }
    
    /**
     * Main routing function - returns optimal model for request
     */
    route(message, context = {}) {
        try {
            this.stats.totalRequests++;
            
            // If routing disabled, use premium model
            if (!this.config.enableRouting) {
                this.log('Routing disabled, using high tier');
                return this.buildResponse('high', 100, 'Routing disabled - using premium model');
            }
            
            // Score the complexity
            const complexityScore = this.scorer.scoreComplexity(message);
            
            // Update running average
            this.updateAverageComplexity(complexityScore);
            
            // Apply context-based adjustments
            const adjustedScore = this.applyContextAdjustments(complexityScore, context);
            
            // Get routing decision
            const decision = this.getRoutingDecision(adjustedScore, message);
            
            // Add timeout information
            if (this.timeoutConfig && this.timeoutConfig.global && this.timeoutConfig.global.enableTimeouts) {
                if (this.timeoutConfig.timeouts && this.timeoutConfig.timeouts.models) {
                    const modelTimeout = this.timeoutConfig.timeouts.models[decision.model];
                    if (modelTimeout) {
                        decision.timeout = modelTimeout.maxResponseTime;
                        decision.retries = modelTimeout.retries;
                    }
                }
            } else {
                // Apply default timeouts based on tier
                const defaultTimeouts = {
                    simple: 30000,
                    medium: 60000,
                    high: 120000,
                    fallback: 180000
                };
                decision.timeout = defaultTimeouts[decision.tier] || 120000;
                decision.retries = decision.tier === 'simple' ? 1 : 2;
            }
            
            // Update stats
            this.stats.routingDecisions[decision.tier]++;
            this.calculateCostSavings();
            
            this.log(`Routed: complexity=${adjustedScore} -> ${decision.tier} (${decision.model})`);
            
            return decision;
            
        } catch (error) {
            this.log('Router error:', error);
            return this.buildResponse('fallback', 100, `Router error: ${error.message}`);
        }
    }
    
    /**
     * Apply context-based complexity adjustments
     */
    applyContextAdjustments(score, context) {
        let adjusted = score;
        
        // User explicitly requested premium model
        if (context.forceHigh || context.model === 'premium') {
            adjusted = 100;
        }
        
        // User explicitly requested simple model
        if (context.forceSimple || context.model === 'simple') {
            adjusted = 0;
        }
        
        // Tool usage typically requires more reasoning
        if (context.toolsRequired && context.toolsRequired.length > 2) {
            adjusted += 20;
        }
        
        // Multi-turn conversation context
        if (context.conversationLength > 10) {
            adjusted += 10; // Longer conversations may need better reasoning
        }
        
        // Time-sensitive requests
        if (context.urgent) {
            // Boost slightly but cap at medium tier for speed
            adjusted = Math.min(65, Math.max(35, adjusted + 10));
        }
        
        return Math.max(0, Math.min(100, adjusted));
    }
    
    /**
     * Get routing decision based on adjusted score
     */
    getRoutingDecision(score, message) {
        message = message || '';

        // ===== TRADING GUARDRAIL (Ankur approved 2026-03-07) =====
        // If ANY trading keyword detected: minimum Kimi, NEVER Gemma
        const isTradingTask = this.capabilities.shouldSkipModel(this.config.models.simple, message);
        if (isTradingTask) {
            if (score > this.config.mediumThreshold) {
                const decision = this.buildResponse('high', score, 'Trading task + high complexity: using Claude Sonnet');
                this.logModelDecision(message, decision, 'TRADING_GUARDRAIL');
                return decision;
            } else {
                const decision = this.buildResponse('medium', score, 'Trading task: bypassing Gemma, using Kimi');
                this.logModelDecision(message, decision, 'TRADING_GUARDRAIL');
                return decision;
            }
        }
        // ===== END TRADING GUARDRAIL =====
        
        // Standard routing based on complexity score
        if (score <= this.config.simpleThreshold) {
            // Verify Gemma can handle it
            if (this.capabilities.canHandle(this.config.models.simple, message, { complexityScore: score })) {
                const decision = this.buildResponse('simple', score, 'Low complexity - using local Gemma');
                this.logModelDecision(message, decision, 'SCORE_BASED');
                return decision;
            } else {
                const decision = this.buildResponse('medium', score, 'Simple score but task requires better model');
                this.logModelDecision(message, decision, 'CAPABILITY_CHECK');
                return decision;
            }
        } else if (score <= this.config.mediumThreshold) {
            const decision = this.buildResponse('medium', score, 'Medium complexity - using Kimi');
            this.logModelDecision(message, decision, 'SCORE_BASED');
            return decision;
        } else {
            const decision = this.buildResponse('high', score, 'High complexity - using Claude Sonnet');
            this.logModelDecision(message, decision, 'SCORE_BASED');
            return decision;
        }
    }
    
    /**
     * Get list of available models in order
     */
    getAvailableModels() {
        return [
            this.config.models.simple,
            this.config.models.medium,
            this.config.models.high,
            this.config.models.fallback
        ];
    }
    
    /**
     * Build standardized response object
     */
    buildResponse(tier, score, reason) {
        return {
            model: this.config.models[tier],
            tier,
            score,
            reason,
            timestamp: new Date().toISOString(),
            fallback: this.config.models.fallback
        };
    }
    
    /**
     * Get fallback routing for errors/timeouts
     */
    getFallbackRouting(originalDecision) {
        this.stats.routingDecisions.fallback++;
        return this.buildResponse('fallback', 100, `Fallback from ${originalDecision && originalDecision.tier ? originalDecision.tier : 'unknown'} tier`);
    }
    
    /**
     * Update running average complexity
     */
    updateAverageComplexity(newScore) {
        const total = this.stats.totalRequests;
        const avg = this.stats.averageComplexity;
        this.stats.averageComplexity = ((avg * (total - 1)) + newScore) / total;
    }
    
    /**
     * Calculate estimated cost savings vs always using premium
     */
    calculateCostSavings() {
        const { simple, medium, high, fallback } = this.stats.routingDecisions;
        const total = simple + medium + high + fallback;
        
        if (total === 0) return;
        
        const freeRequests = simple + medium;
        this.stats.costSavings = (freeRequests / total) * 100;
    }
    
    /**
     * Get current routing statistics
     */
    getStats() {
        const total = this.stats.totalRequests || 1;
        return {
            ...this.stats,
            distribution: {
                simple: (this.stats.routingDecisions.simple / total * 100).toFixed(1) + '%',
                medium: (this.stats.routingDecisions.medium / total * 100).toFixed(1) + '%', 
                high: (this.stats.routingDecisions.high / total * 100).toFixed(1) + '%',
                fallback: (this.stats.routingDecisions.fallback / total * 100).toFixed(1) + '%'
            },
            averageComplexity: Math.round(this.stats.averageComplexity),
            estimatedSavings: Math.round(this.stats.costSavings) + '%'
        };
    }
    
    /**
     * Reset statistics
     */
    resetStats() {
        this.stats = {
            totalRequests: 0,
            routingDecisions: { simple: 0, medium: 0, high: 0, fallback: 0 },
            averageComplexity: 0,
            costSavings: 0
        };
        this.log('Statistics reset');
    }
    
    /**
     * Update configuration
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        this.log('Configuration updated', newConfig);
    }

    /**
     * Log every routing decision to logs/routing.log for audit trail
     */
    logModelDecision(message, decision, routingReason) {
        if (!this.config.enableLogging) return;
        
        try {
            const logsDir = path.join(__dirname, '..', 'logs');
            if (!fs.existsSync(logsDir)) {
                fs.mkdirSync(logsDir, { recursive: true });
            }
            
            const entry = JSON.stringify({
                ts: new Date().toISOString(),
                msg: message.substring(0, 80).replace(/\n/g, ' '),
                model: decision.model,
                tier: decision.tier,
                score: decision.score,
                routing_reason: routingReason,
                decision_reason: decision.reason
            });
            
            fs.appendFileSync(path.join(logsDir, 'routing.log'), entry + '\n');
        } catch (err) {
            // Never crash the router over logging
            console.error('[Smart Router] Log write failed:', err.message);
        }
    }
    
    /**
     * Internal logging
     */
    log(message, data) {
        if (!this.config.enableLogging) return;
        
        const timestamp = new Date().toISOString();
        const logEntry = `[${timestamp}] Smart Router: ${message}`;
        
        if (data) {
            console.log(logEntry, data);
        } else {
            console.log(logEntry);
        }
    }
}

module.exports = RouterEngine;
