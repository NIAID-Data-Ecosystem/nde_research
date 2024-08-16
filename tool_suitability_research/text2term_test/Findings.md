### Text2Term weaknesses against locations names for species mapping
Certain locations exist as species names in the NCBI Taxonomy. Text2Term will happily map anything that is pulled out by EXTRACT, and is not able to readily distinguish if a term mentioned was actually a species or if it was isolated from a specific location. Given the likelihood of mentions for locations to be much higher than the mentions of very specific species with the same name as those locations, we can improve the accuracy of the results by simply dropping all extracted and mapped location names.

Additionally, there may be other terms that frequently appear that are likely to represent something other than a species mention. Those terms which will consistently be picked up by EXTRACT and successfully mapped by T2T should also be dropped if the likelihood of them being irrelevant is very high relative to the likelihood of them being correct.

### Potential heuristics for improving the quality of the results
* Text2Term is weaker at mapping terms with fewer letters so a score cut off should be applied for terms with 3 letters, 4 letters, and 5 letters
  * For 3 letter terms
    * The capitalization will not affect the match terms
    * A match score of >0.95 is likely to be correct
    * However, the number of extracted terms that are likely to be true terms vs false positives is only 12/48 even after meeting this threshhold. For this reason, we should exclude terms of 3 or less characters as the percentage EXTRACTed correctly is pretty low
  * For 4 letter terms
    * At a score of >0.95, cats, rats and bats will be false negatives (matched well, but dropped), while duck (matched a little too specifically to domestic duck) will pass
    * At a score of >0.91, cats, rats, and bats will pass, duck will still be an issue
    * However, the number of extracted terms that are likely to be true terms is only ~42/181. For this reason, we should also exclude terms of 4 or less characters
  * For 5 letter terms
    * At a score of >0.95, the number of true positives is 91/127
    * Of those 91 true positive terms, about 41 are terms which are part of a taxonomic phrase (i.e. - either only the genus part of a taxonomy or a species part
    * This means that only about 41 of these terms would be missed with the number of letters threshhold for EXTRACT were >5, the remaining true positives would likely be captured with the whole term
* Text2Term is also weaker at mapping terms formatted as g. species, as it can score higher mapping to the correct species term but incorrect genus. To address this:
  * Identify such terms using regex `(r"\b[A-Z].\s[^\s]+\b")`
    * For these terms, only take the result if the genus letter matches the first letter of the mapped result (i.e. split on '.', take first)
    * There will be plenty of exceptions, but this should address the majority of problematic matches
* Default behavior if prior conditions don't apply:
  * Sort by score (highest to lowest), keep first
