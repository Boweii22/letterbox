import datetime as dt
import unittest
from server import match_quote, verify_details, explicit_dates, make_calendar, source_candidates, SAMPLES

class EvidenceTests(unittest.TestCase):
    def test_quote_match_preserves_original_offsets(self):
        text='Header\n\nPlease pay £48.50\nby 20 October 2026.\nThank you.'
        span=match_quote(text,'Please pay £48.50 by 20 October 2026.')
        self.assertEqual(text[span['start']:span['end']], 'Please pay £48.50\nby 20 October 2026.')

    def test_changed_digit_is_rejected(self):
        self.assertIsNone(match_quote('Please pay £48.50 by 20 October 2026.', 'Please pay £48.50 by 21 October 2026.'))

    def test_short_and_absent_quotes_rejected(self):
        self.assertIsNone(match_quote('Please return your books.', 'Please'))
        self.assertIsNone(match_quote('Please return your books.', 'You must pay a fine immediately.'))

    def test_consistent_ocr_error_is_not_detected(self):
        # Deliberately demonstrates the limit: this is not original-image verification.
        transcribed='Your appointment is on 15 November 2026.'
        self.assertIsNotNone(match_quote(transcribed, transcribed))

    def test_misinterpretation_can_still_match(self):
        text='If you have already paid, please ignore this reminder.'
        result=verify_details(text, {'details':[{'kind':'action','explanation':'Ignore the reminder.','quote':text}]})
        self.assertTrue(result[0]['matched'])
        self.assertNotIn('verified', result[0])

    def test_invalid_model_list_rejected(self):
        with self.assertRaises(ValueError): verify_details('Example source letter.', {'details':'bad'})

    def test_matching_quote_does_not_allow_invented_date(self):
        text='Please arrive 10 minutes before your appointment.'
        result=verify_details(text, {'details':[{'kind':'date','explanation':'15 October 2026','quote':text}]})
        self.assertTrue(result[0]['matched'])
        self.assertFalse(result[0]['supported'])
        self.assertEqual(len(result[0]['issues']),2)

    def test_browser_offsets_handle_emoji(self):
        text='✉️ 📬 Please return your books.'
        result=verify_details(text, {'details':[{'kind':'action','explanation':'Return your books.','quote':'Please return your books.'}]})
        self.assertEqual(result[0]['span']['start'],len('✉️ 📬 '.encode('utf-16-le'))//2)

    def test_relative_and_numeric_dates_not_guessed(self):
        self.assertEqual(explicit_dates('Return within 14 days. Date: 05/06/26.'), [])
        self.assertEqual(explicit_dates('By 31 February 2026.'), [])
        self.assertEqual(explicit_dates('By 20 October 2026.'), ['2026-10-20'])

    def test_source_selection_preserves_relative_deadline(self):
        candidates=source_candidates(SAMPLES['ambiguous']['text'])
        self.assertEqual(candidates[0]['kind'],'date')
        self.assertIn('within 14 days',candidates[0]['quote'])
        self.assertEqual(explicit_dates(candidates[0]['quote']),[])

    def test_ocr_wrapped_lines_join_without_inventing_quote(self):
        text='NORTHBRIDGE\nDear Alex,\nYour appointment is on 15 October 2026 at\n10:30 AM at the clinic.\nPlease bring your letter.'
        candidates=source_candidates(text)
        self.assertEqual(len(candidates),2)
        self.assertTrue(all(match_quote(text,c['quote']) for c in candidates))

class NumericOmissionTests(unittest.TestCase):
    def test_date_replaced_with_unrelated_instruction_is_flagged(self):
        quote='Your appointment is on 15 October 2026 at 10:30 AM.'
        detail=verify_details(quote,{'details':[{'kind':'date','quote':quote,'explanation':'Please bring your letter.'}]})[0]
        self.assertFalse(detail['supported'])
        self.assertIn('omits numeric',detail['issues'][0])

    def test_amount_missing_from_summary_is_flagged(self):
        quote='The outstanding balance is £48.50.'
        detail=verify_details(quote,{'details':[{'kind':'amount','quote':quote,'explanation':'There is an outstanding balance.'}]})[0]
        self.assertFalse(detail['supported'])

class CalendarTests(unittest.TestCase):
    def test_unconfirmed_date_rejected(self):
        with self.assertRaises(ValueError): make_calendar('2026-10-20','Reminder','Please pay by 20 October 2026.',False)
        with self.assertRaises(ValueError): make_calendar('2026-10-20','Reminder','Source','yes')

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError): make_calendar('2026-02-31','Reminder','Source',True)

    def test_all_day_event_escaping_and_folding(self):
        calendar=make_calendar('2026-12-31','Review; hello, world\nBEGIN:VEVENT','£'*200,True)
        self.assertIn('DTSTART;VALUE=DATE:20261231',calendar)
        self.assertIn('DTEND;VALUE=DATE:20270101',calendar)
        self.assertIn('Review\\; hello\\, world\\nBEGIN:VEVENT',calendar)
        self.assertEqual(calendar.count('\r\nBEGIN:VEVENT\r\n'),1)
        self.assertTrue(all(len(line.encode())<=75 for line in calendar.split('\r\n')))

if __name__=='__main__': unittest.main()
