export const CaseStatus = {
    ACTIVE: "ACTIVE",
    PENDING: "PENDING",
    CLOSED: "CLOSED",
    ARCHIVED: "ARCHIVED",
    ON_HOLD: "ON_HOLD"
} as const;
export type CaseStatus = (typeof CaseStatus)[keyof typeof CaseStatus];

export const CasePriority = {
    LOW: "LOW",
    MEDIUM: "MEDIUM",
    HIGH: "HIGH",
    URGENT: "URGENT"
} as const;
export type CasePriority = (typeof CasePriority)[keyof typeof CasePriority];

export const CaseType = {
    CIVIL: "CIVIL",
    CRIMINAL: "CRIMINAL",
    FAMILY: "FAMILY",
    CORPORATE: "CORPORATE",
    IMMIGRATION: "IMMIGRATION",
    PERSONAL_INJURY: "PERSONAL_INJURY",
    REAL_ESTATE: "REAL_ESTATE",
    BANKRUPTCY: "BANKRUPTCY",
    INTELLECTUAL_PROPERTY: "INTELLECTUAL_PROPERTY",
    OTHER: "OTHER"
} as const;
export type CaseType = (typeof CaseType)[keyof typeof CaseType];

export interface Case {
    id: string;
    case_number: string;
    title: string;
    description?: string;
    case_type: CaseType | string; // Allow string for flexibility if backend returns varied case
    status: CaseStatus | string;
    priority: CasePriority | string;
    client_id?: string;
    
    // Court information
    court_name?: string;
    judge_name?: string;
    case_jurisdiction?: string;
    
    // Important dates
    filed_date?: string;
    court_date?: string;
    deadline_date?: string;
    closed_date?: string;
    
    // AI-generated fields
    ai_category?: string;
    ai_summary?: string;
    ai_keywords?: string[];
    ai_risk_assessment?: any; // JSON structure
    
    created_at: string;
    updated_at?: string;
    
    // Timeline placeholder until strictly typed
    timeline?: any[];
}
