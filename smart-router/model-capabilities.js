/**
 * Model Capabilities Matrix
 * Defines what each model can and cannot handle
 */

class ModelCapabilities {
    constructor() {
        this.models = {
            'ollama/gemma2:2b': {
                name: 'Gemma 2B',
                tier: 'simple',
                capabilities: {
                    conversation: true,
                    simpleQA: true,
                    basicMath: true,
                    shortResponses: true,
                    factRetrieval: true
                },
                limitations: {
                    maxResponseLength: 100,
                    maxComplexity: 30,
                    noCodeGeneration: true,
                    noAnalysis: true,
                    noToolUsage: true,
                    noReasoning: true,
                    noLongContext: true
                },
                performance: {
                    avgResponseTime: 2000,
                    maxResponseTime: 30000,
                    reliability: 0.85
                }
            },
            
            'nvidia-nim/moonshotai/kimi-k2.5': {
                name: 'Kimi K2.5',
                tier: 'medium',
                capabilities: {
                    conversation: true,
                    complexQA: true,
                    analysis: true,
                    reasoning: true,
                    mediumContext: true,
                    toolUsage: true,
                    codeGeneration: true
                },
                limitations: {
                    maxResponseLength: 2000,
                    maxComplexity: 70,
                    limitedCreativity: true,
                    noDeepReasoning: true
                },
                performance: {
                    avgResponseTime: 5000,
                    maxResponseTime: 60000,
                    reliability: 0.92
                }
            },
            
            'anthropic/claude-sonnet-4-20250514': {
                name: 'Claude Sonnet',
                tier: 'high',
                capabilities: {
                    everything: true,
                    deepAnalysis: true,
                    complexReasoning: true,
                    creativeWriting: true,
                    advancedCoding: true,
                    longContext: true,
                    multiToolUsage: true
                },
                limitations: {
                    costPerRequest: 'high',
                    rateLimit: true
                },
                performance: {
                    avgResponseTime: 8000,
                    maxResponseTime: 120000,
                    reliability: 0.98
                }
            },
            
            'anthropic/claude-opus-4-20250514': {
                name: 'Claude Opus',
                tier: 'ultimate',
                capabilities: {
                    everything: true,
                    ultimateReasoning: true,
                    complexProblems: true,
                    researchGrade: true,
                    perfectAccuracy: true
                },
                limitations: {
                    costPerRequest: 'very-high',
                    rateLimit: true,
                    slower: true
                },
                performance: {
                    avgResponseTime: 12000,
                    maxResponseTime: 180000,
                    reliability: 0.99
                }
            }
        };
        
        this.taskPatterns = {
            skipGemma: [
                // Analysis patterns
                /analyz/i, /analysis/i, /evaluate/i, /compare/i, /assess/i,
                
                // Code patterns  
                /code/i, /function/i, /implement/i, /algorithm/i, /debug/i,
                /python/i, /javascript/i, /program/i, /script/i,
                
                // Complex reasoning
                /explain.*how/i, /why.*does/i, /reasoning/i, /think.*through/i,
                /step.*by.*step/i, /complex/i, /detailed/i,
                
                // Tool usage
                /search/i, /browse/i, /fetch/i, /scrape/i, /read.*file/i,
                
                // Long form
                /write.*article/i, /create.*report/i, /comprehensive/i,
                /full.*analysis/i, /in-depth/i,

                // ===== TRADING KEYWORD BYPASS (Ankur approved 2026-03-07) =====
                // Trading core - NEVER route to Gemma
                /\btrade\b/i, /\bsignal\b/i, /\bwhale\b/i, /\bmarket\b/i,
                /\bpolymarket\b/i, /\bprice\b/i, /\bposition\b/i, /\bkelly\b/i,
                /\bbuy\b/i, /\bsell\b/i, /\bentry\b/i, /\bexit\b/i,
                
                // Paper trading
                /\bpaper\b/i, /\bproposal\b/i, /\bapprove\b/i, /\breject\b/i,
                /\bexecute\b/i, /\btier\b/i, /\bdivergence\b/i,
                
                // Portfolio & financial
                /\bbalance\b/i, /\bledger\b/i, /\bpnl\b/i, /\bprofit\b/i,
                /\bloss\b/i, /\bexposure\b/i, /\bportfolio\b/i, /\bwallet\b/i,
                /\busdc\b/i, /\bstake\b/i, /\bbet\b/i,
                
                // Market specific
                /\boscar\b/i, /\bmasters\b/i, /\bfed\b/i, /\binflation\b/i,
                /\bbitcoin\b/i, /\bbtc\b/i, /\beth\b/i, /\bcrypto\b/i,
                /\bresolve\b/i, /\bresolution\b/i, /\btariff\b/i,
                
                // System ops (trading-related)
                /\bcron\b/i, /\bbridge\b/i, /\bscan\b/i, /\btracker\b/i,
                /\bscorecard\b/i, /\bwatchlist\b/i, /\bhedge\b/i
                // ===== END TRADING KEYWORD BYPASS =====
            ],
            
            requiresClaude: [
                // Very complex
                /financial.*model/i, /dcf.*analysis/i, /monte.*carlo/i,
                /machine.*learning/i, /deep.*dive/i, /research.*paper/i,
                
                // Creative
                /creative.*writing/i, /story/i, /novel/i, /poetry/i,
                
                // Multiple tools
                /and.*then.*and/i, /multiple.*steps/i, /workflow/i
            ]
        };
    }
    
    /**
     * Check if a model can handle a specific task
     */
    canHandle(model, message, context = {}) {
        const modelInfo = this.models[model];
        if (!modelInfo) return false;
        
        // Check message length
        const messageLength = message.length;
        if (modelInfo.limitations.maxResponseLength && 
            messageLength > modelInfo.limitations.maxResponseLength * 0.5) {
            return false;
        }
        
        // Check for patterns that skip Gemma
        if (model === 'ollama/gemma2:2b') {
            for (const pattern of this.taskPatterns.skipGemma) {
                if (pattern.test(message)) {
                    return false;
                }
            }
        }
        
        // Check if task requires Claude
        for (const pattern of this.taskPatterns.requiresClaude) {
            if (pattern.test(message)) {
                return model.includes('claude');
            }
        }
        
        // Check tool usage context
        if (context.toolsRequired && context.toolsRequired.length > 0) {
            return modelInfo.capabilities.toolUsage === true;
        }
        
        // Check complexity score
        if (context.complexityScore) {
            const maxComplexity = modelInfo.limitations.maxComplexity || 100;
            return context.complexityScore <= maxComplexity;
        }
        
        return true;
    }
    
    /**
     * Get the best model for a specific task
     */
    getBestModel(message, availableModels, context = {}) {
        // Filter models that can handle the task
        const capableModels = availableModels.filter(model => 
            this.canHandle(model, message, context)
        );
        
        if (capableModels.length === 0) {
            // No capable models, return the most capable available
            return availableModels[availableModels.length - 1];
        }
        
        // Return the first capable model (ordered by preference)
        return capableModels[0];
    }
    
    /**
     * Get model performance stats
     */
    getPerformanceStats(model) {
        const modelInfo = this.models[model];
        return modelInfo ? modelInfo.performance : null;
    }
    
    /**
     * Check if model should skip based on pattern
     */
    shouldSkipModel(model, message) {
        if (model === 'ollama/gemma2:2b') {
            return this.taskPatterns.skipGemma.some(pattern => pattern.test(message));
        }
        return false;
    }
}

module.exports = ModelCapabilities;