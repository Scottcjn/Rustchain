// Add a test to ensure the status filter is working correctly
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_status_filter() {
        // Arrange
        let open_bounties = vec![Bounty { status: "open" }];
        let closed_bounties = vec![Bounty { status: "closed" }];

        // Act
        let filtered_bounties = _fetch_bounties("open");

        // Assert
        assert_eq!(filtered_bounties, open_bounties);
    }
}

// Modify the _fetch_bounties function to include the status filter
fn _fetch_bounties(status: &str) -> Vec<Bounty> {
    // Existing code...
    let mut bounties = vec![];

    // Filter bounties by status
    if status == "open" {
        bounties = bounties.into_iter().filter(|bounty| bounty.status == "open").collect();
    } else if status == "closed" {
        bounties = bounties.into_iter().filter(|bounty| bounty.status == "closed").collect();
    }

    bounties
}