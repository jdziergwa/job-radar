export interface ExperienceEntry {
  company: string;
  role: string;
  dates: string;
  industry?: string;
  highlights: string[];
}

export interface EducationEntry {
  school: string;
  degree: string;
  start_year?: string;
  end_year?: string;
}

export interface PortfolioEntry {
  name: string;
  url: string;
  technologies: string[];
  description?: string;
}

export interface CVAnalysisResponse {
  page_count: number;
  current_role: string;
  experience_years?: number;
  experience_summary: string;
  experience: ExperienceEntry[];
  skills: Record<string, string[]>;
  education: EducationEntry[];
  portfolio: PortfolioEntry[];
  spoken_languages: string[];
  inferred_seniority: string;
  suggested_target_roles: string[];
  suggested_title_patterns: Record<string, string[]>;
  suggested_description_signals: string[];
  suggested_exclusions: string[];
  suggested_skill_gaps: string[];
  suggested_career_direction: string;
  suggested_good_match_signals: string[];
  suggested_lower_fit_signals: string[];
}

export interface UserPreferences {
  target_roles: string[];
  seniority: string;
  location: string;
  work_authorization: string;
  remote_preference: string;
  target_regions: string[];
  excluded_regions: string[];
  industries: string[];
  career_direction: string;
  good_match_signals: string[];
  deal_breakers: string[];
  additional_context: string;
}

export interface ProfileGenerateRequest {
  cv_analysis: CVAnalysisResponse;
  user_preferences: UserPreferences;
  profile_name: string;
}

export interface ProfileGenerateResponse {
  profile_yaml: string;
  profile_doc: string;
}

export interface ProfileSaveRequest {
  profile_name: string;
  profile_yaml: string;
  profile_doc: string;
}
