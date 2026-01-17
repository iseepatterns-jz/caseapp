"""
Timeline export service for generating various formats (PDF, PNG, JSON)
"""

import asyncio
import os
import json
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import structlog
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from services.timeline_service import TimelineService
from services.audit_service import AuditService
from models.timeline import TimelineEvent
from schemas.timeline import TimelineExportRequest

logger = structlog.get_logger()

class TimelineExportService:
    """Service for exporting timelines in various formats"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        audit_service = AuditService(db)
        self.timeline_service = TimelineService(db, audit_service)
        
    async def export_case_timeline(
        self,
        case_id: UUID,
        export_request: TimelineExportRequest,
        user_id: UUID
    ) -> str:
        """
        Export case timeline in the requested format
        
        Args:
            case_id: Case UUID
            export_request: Export configuration
            user_id: User requesting the export
            
        Returns:
            File path of the exported timeline
        """
        try:
            # Get timeline events for the case
            events, total_count = await self.timeline_service.get_case_timeline(
                case_id=case_id,
                start_date=export_request.start_date,
                end_date=export_request.end_date,
                event_types=[et.value for et in export_request.event_types] if export_request.event_types else None,
                limit=1000,  # Large limit for export
                offset=0
            )
            
            if not events:
                raise ValueError("No timeline events found for export")
            
            # Prepare export data
            export_data = await self._prepare_export_data(
                case_id, events, export_request, user_id
            )
            
            # Export based on format
            if export_request.format == "pdf":
                filepath = await self._export_pdf(export_data)
            elif export_request.format == "png":
                filepath = await self._export_png(export_data)
            elif export_request.format == "json":
                filepath = await self._export_json(export_data)
            else:
                raise ValueError(f"Unsupported export format: {export_request.format}")
            
            logger.info(
                "Timeline exported successfully",
                case_id=str(case_id),
                format=export_request.format,
                events_count=len(events),
                user_id=str(user_id)
            )
            
            return filepath
            
        except Exception as e:
            logger.error("Timeline export failed", case_id=str(case_id), error=str(e))
            raise
    
    async def _prepare_export_data(
        self,
        case_id: UUID,
        events: List[TimelineEvent],
        export_request: TimelineExportRequest,
        user_id: UUID
    ) -> Dict[str, Any]:
        """Prepare data structure for export"""
        
        # Convert events to export format
        export_events = []
        for event in events:
            event_data = {
                "id": str(event.id),
                "title": event.title,
                "description": event.description or "",
                "event_type": event.event_type,
                "event_date": event.event_date.isoformat(),
                "end_date": event.end_date.isoformat() if event.end_date else None,
                "all_day": event.all_day,
                "location": event.location or "",
                "participants": event.participants or [],
                "importance_level": event.importance_level,
                "is_milestone": event.is_milestone,
                "display_order": event.display_order or 0,
                "color": event.color,
                "created_at": event.created_at.isoformat(),
                "created_by": str(event.created_by)
            }
            
            # Add evidence pins if requested
            if export_request.include_evidence and event.evidence_pins:
                event_data["evidence_pins"] = []
                for pin in event.evidence_pins:
                    pin_data = {
                        "id": str(pin.id),
                        "evidence_type": pin.evidence_type,
                        "evidence_id": str(pin.evidence_id),
                        "relevance_score": pin.relevance_score,
                        "pin_description": pin.pin_description or "",
                        "pin_notes": pin.pin_notes or "",
                        "is_primary": pin.is_primary,
                        "display_order": pin.display_order
                    }
                    event_data["evidence_pins"].append(pin_data)
            
            # Add comments if requested
            if export_request.include_comments and event.comments:
                event_data["comments"] = []
                for comment in event.comments:
                    comment_data = {
                        "id": str(comment.id),
                        "comment_text": comment.comment_text,
                        "is_internal": comment.is_internal,
                        "created_at": comment.created_at.isoformat(),
                        "created_by": str(comment.created_by)
                    }
                    event_data["comments"].append(comment_data)
            
            export_events.append(event_data)
        
        # Calculate statistics
        total_events = len(export_events)
        events_with_evidence = sum(1 for e in export_events if e.get("evidence_pins"))
        total_evidence_pins = sum(len(e.get("evidence_pins", [])) for e in export_events)
        milestone_events = sum(1 for e in export_events if e["is_milestone"])
        
        # Event type distribution
        event_type_counts = {}
        for event in export_events:
            event_type = event["event_type"]
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        
        # Date range
        if export_events:
            dates = [datetime.fromisoformat(e["event_date"]) for e in export_events]
            date_range = {
                "start": min(dates).isoformat(),
                "end": max(dates).isoformat()
            }
        else:
            date_range = {"start": None, "end": None}
        
        return {
            "case_id": str(case_id),
            "title": export_request.title or f"Case Timeline - {case_id}",
            "export_format": export_request.format,
            "exported_at": datetime.now(UTC).isoformat(),
            "exported_by": str(user_id),
            "events": export_events,
            "statistics": {
                "total_events": total_events,
                "events_with_evidence": events_with_evidence,
                "total_evidence_pins": total_evidence_pins,
                "milestone_events": milestone_events,
                "event_type_distribution": event_type_counts,
                "date_range": date_range
            },
            "export_options": {
                "include_evidence": export_request.include_evidence,
                "include_comments": export_request.include_comments,
                "start_date": export_request.start_date.isoformat() if export_request.start_date else None,
                "end_date": export_request.end_date.isoformat() if export_request.end_date else None,
                "event_types": [et.value for et in export_request.event_types] if export_request.event_types else None
            }
        }
    
    async def _export_pdf(self, export_data: Dict[str, Any]) -> str:
        """Export timeline as PDF document"""
        
        filename = f"timeline_{export_data['case_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = f"/tmp/{filename}"
        
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Build PDF content
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#1976D2')
        )
        
        event_title_style = ParagraphStyle(
            'EventTitle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#333333')
        )
        
        # Title page
        story.append(Paragraph(export_data['title'], title_style))
        story.append(Spacer(1, 12))
        
        # Timeline metadata
        stats = export_data['statistics']
        metadata_data = [
            ['Case ID:', export_data['case_id']],
            ['Export Date:', datetime.fromisoformat(export_data['exported_at']).strftime('%B %d, %Y at %I:%M %p')],
            ['Total Events:', str(stats['total_events'])],
            ['Events with Evidence:', str(stats['events_with_evidence'])],
            ['Milestone Events:', str(stats['milestone_events'])],
        ]
        
        if stats['date_range']['start']:
            start_date = datetime.fromisoformat(stats['date_range']['start']).strftime('%B %d, %Y')
            end_date = datetime.fromisoformat(stats['date_range']['end']).strftime('%B %d, %Y')
            metadata_data.append(['Date Range:', f"{start_date} - {end_date}"])
        
        metadata_table = Table(metadata_data, colWidths=[2*inch, 3*inch])
        metadata_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(metadata_table)
        story.append(Spacer(1, 24))
        story.append(PageBreak())
        
        # Timeline events
        story.append(Paragraph("Timeline Events", styles['Heading1']))
        story.append(Spacer(1, 12))
        
        for event in export_data['events']:
            # Event header
            event_date = datetime.fromisoformat(event['event_date'])
            date_str = event_date.strftime('%B %d, %Y at %I:%M %p')
            
            title_text = event['title']
            if event['is_milestone']:
                title_text = f"🏆 {title_text} (Milestone)"
            
            story.append(Paragraph(title_text, event_title_style))
            
            # Event details table
            event_details = [
                ['Date:', date_str],
                ['Type:', event['event_type'].replace('_', ' ').title()],
                ['Importance:', f"{event['importance_level']}/5"],
            ]
            
            if event.get('location'):
                event_details.append(['Location:', event['location']])
            
            if event.get('participants'):
                event_details.append(['Participants:', ', '.join(event['participants'])])
            
            details_table = Table(event_details, colWidths=[1.5*inch, 4*inch])
            details_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, grey),
            ]))
            
            story.append(details_table)
            story.append(Spacer(1, 6))
            
            # Event description
            if event.get('description'):
                story.append(Paragraph(f"<b>Description:</b> {event['description']}", styles['Normal']))
                story.append(Spacer(1, 6))
            
            # Evidence section
            if event.get('evidence_pins'):
                story.append(Paragraph("<b>Evidence:</b>", styles['Normal']))
                
                evidence_data = []
                for pin in event['evidence_pins']:
                    evidence_type = pin['evidence_type'].title()
                    relevance = f"{pin['relevance_score']:.1f}/1.0"
                    primary = "Yes" if pin['is_primary'] else "No"
                    description = pin['pin_description'][:50] + ('...' if len(pin['pin_description']) > 50 else '')
                    
                    evidence_data.append([
                        evidence_type,
                        str(pin['evidence_id'])[:8] + '...',
                        relevance,
                        primary,
                        description
                    ])
                
                if evidence_data:
                    evidence_table = Table(
                        [['Type', 'Evidence ID', 'Relevance', 'Primary', 'Description']] + evidence_data,
                        colWidths=[0.8*inch, 1.2*inch, 0.8*inch, 0.6*inch, 2.2*inch]
                    )
                    evidence_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#E3F2FD')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('GRID', (0, 0), (-1, -1), 0.5, grey),
                    ]))
                    
                    story.append(evidence_table)
            
            story.append(Spacer(1, 18))
        
        # Build PDF
        doc.build(story)
        
        logger.info("Timeline PDF exported", case_id=export_data['case_id'], filepath=filepath)
        return filepath
    
    async def _export_png(self, export_data: Dict[str, Any]) -> str:
        """Export timeline as PNG visualization"""
        
        events = export_data['events']
        if not events:
            raise ValueError("No events to visualize")
        
        # Set up the plot
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(16, max(8, len(events) * 0.8)))
        
        # Parse dates and prepare data
        dates = []
        event_names = []
        importance_colors = {
            1: '#E3F2FD',  # Very Low - Light Blue
            2: '#90CAF9',  # Low - Light Blue
            3: '#42A5F5',  # Medium - Blue
            4: '#FF9800',  # High - Orange
            5: '#F44336'   # Critical - Red
        }
        
        colors = []
        evidence_counts = []
        
        for event in events:
            event_date = datetime.fromisoformat(event['event_date'])
            dates.append(event_date)
            
            # Truncate long titles
            title = event['title']
            if len(title) > 40:
                title = title[:37] + '...'
            event_names.append(title)
            
            colors.append(importance_colors.get(event['importance_level'], '#42A5F5'))
            evidence_counts.append(len(event.get('evidence_pins', [])))
        
        # Create timeline visualization
        y_positions = range(len(events))
        
        # Plot events as horizontal bars
        bars = ax.barh(y_positions, [1] * len(events), 
                      left=[mdates.date2num(d) for d in dates],
                      height=0.6, color=colors, alpha=0.8, edgecolor='black')
        
        # Add event labels
        for i, (date, name, evidence_count, event) in enumerate(zip(dates, event_names, evidence_counts, events)):
            # Event title with milestone indicator
            title_text = name
            if event['is_milestone']:
                title_text = f"🏆 {title_text}"
            
            ax.text(mdates.date2num(date) + 0.5, i, title_text, 
                   va='center', ha='left', fontweight='bold', fontsize=10)
            
            # Evidence indicator
            if evidence_count > 0:
                ax.text(mdates.date2num(date) - 0.5, i, f'📎{evidence_count}', 
                       va='center', ha='right', fontsize=8)
        
        # Format the plot
        ax.set_yticks(y_positions)
        ax.set_yticklabels([d.strftime('%m/%d/%Y') for d in dates])
        ax.set_xlabel('Timeline', fontsize=12, fontweight='bold')
        ax.set_title(export_data['title'], fontsize=16, fontweight='bold', pad=20)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d/%Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Add legend for importance levels
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, alpha=0.8, label=f'Level {level}') 
                          for level, color in importance_colors.items()]
        ax.legend(handles=legend_elements, loc='upper right', title='Importance Level')
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Adjust layout
        plt.tight_layout()
        
        # Save file
        filename = f"timeline_{export_data['case_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = f"/tmp/{filename}"
        
        plt.savefig(filepath, format='png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("Timeline PNG exported", case_id=export_data['case_id'], filepath=filepath)
        return filepath
    
    async def _export_json(self, export_data: Dict[str, Any]) -> str:
        """Export timeline as structured JSON"""
        
        filename = f"timeline_{export_data['case_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"/tmp/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info("Timeline JSON exported", case_id=export_data['case_id'], filepath=filepath)
        return filepath